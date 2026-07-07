import asyncio
import logging
import struct
from .crypto import AuthPackets, SRP6
from .packets import Opcodes

logger = logging.getLogger("AuthSession")

class AuthSession:
    """
    Maneja el socket TCP para el Auth Server (puerto 3724).
    Responsabilidad: Login, SRP6 challenge/proof y obtención del Realm List.
    """
    def __init__(self, host: str, port: int = 3724):
        self.host = host
        self.port = port
        
    async def authenticate(self, account: str, password: str) -> dict:
        """
        Ejecuta la Fase 4D: Autenticación completa con SRP6a.
        """
        logger.info(f"Iniciando Fase 4D: Autenticación completa para {account} en {self.host}")
        
        try:
            reader, writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), 
                timeout=5.0
            )
        except Exception as e:
            return {"status": "SOCKET_ERROR", "details": str(e)}

        try:
            # 1. Enviar AUTH_LOGON_CHALLENGE
            packet = AuthPackets.build_logon_challenge(account)
            writer.write(packet)
            await writer.drain()
            
            # 2. Recibir CHALLENGE Response
            header = await asyncio.wait_for(reader.read(3), timeout=5.0)
            if not header or len(header) < 3:
                return {"status": "AUTH_PROTOCOL_ERROR", "details": "Cabecera de respuesta incompleta."}

            cmd, error, result = struct.unpack('<BBB', header)
            if cmd != 0x00:
                return {"status": "UNKNOWN_RESPONSE", "details": f"Esperado 0x00, recibido 0x{cmd:02x}"}
            
            if result != 0:
                return {"status": "AUTH_REJECTED", "details": f"Challenge rechazado (Result: {result})"}

            # Leer el resto del payload del challenge
            # Estructura: B[32], g_len[1], g[g_len], N_len[1], N[N_len], salt[32], unk[16], security[1]
            payload = await reader.read(1024) # Leer suficiente para el challenge
            
            # Parsear payload
            offset = 0
            B_bytes = payload[offset:offset+32]; offset += 32
            g_len = payload[offset]; offset += 1
            g_bytes = payload[offset:offset+g_len]; offset += g_len
            N_len = payload[offset]; offset += 1
            N_bytes = payload[offset:offset+N_len]; offset += N_len
            salt_bytes = payload[offset:offset+32]; offset += 32
            
            logger.info("Challenge recibido y parseado. Calculando SRP6 Proof...")
            
            # 3. Matemática SRP6
            srp = SRP6(account, password)
            A_bytes = srp.get_A(int.from_bytes(g_bytes, 'little'), int.from_bytes(N_bytes, 'little'))
            M1 = srp.calculate_M1(B_bytes, salt_bytes, g_bytes, N_bytes)
            
            # 4. Enviar AUTH_LOGON_PROOF
            proof_packet = AuthPackets.build_logon_proof(A_bytes, M1)
            writer.write(proof_packet)
            await writer.drain()
            logger.info("AUTH_LOGON_PROOF enviado.")
            
            # 5. Recibir PROOF Response
            proof_res = await asyncio.wait_for(reader.read(1024), timeout=5.0)
            if not proof_res or len(proof_res) < 2:
                return {"status": "AUTH_PROTOCOL_ERROR", "details": "Sin respuesta al proof."}
            
            res_cmd, res_error = struct.unpack('<BB', proof_res[:2])
            if res_cmd != 0x01:
                 return {"status": "UNKNOWN_RESPONSE", "details": f"Esperado 0x01, recibido 0x{res_cmd:02x}"}
            
            if res_error != 0:
                return {"status": "AUTH_PROOF_REJECTED", "details": f"Proof rechazado (Error: {res_error})"}

            logger.info("¡Autenticación aceptada! Solicitando lista de reinos...")
            
            # 6. Solicitar REALM_LIST (Opcode 0x10)
            writer.write(struct.pack('<B I', 0x10, 0))
            await writer.drain()
            
            realm_data = await asyncio.wait_for(reader.read(4096), timeout=5.0)
            if not realm_data or realm_data[0] != 0x10:
                return {"status": "REALM_LIST_ERROR", "details": "No se recibió la lista de reinos."}
            
            # Parseo Real del Protocolo 3.3.5a
            realms = []
            try:
                # Cabecera: Opcode[1], Size[2], Unk[4], Count[2]
                count = struct.unpack('<H', realm_data[7:9])[0]
                offset = 9
                
                for _ in range(count):
                    r_type = realm_data[offset]; offset += 1
                    r_locked = realm_data[offset]; offset += 1
                    r_flags = realm_data[offset]; offset += 1
                    
                    # Nombre (string\0)
                    end = realm_data.find(b'\x00', offset)
                    r_name = realm_data[offset:end].decode('ascii'); offset = end + 1
                    
                    # Dirección (string\0) -> "IP:PORT"
                    end = realm_data.find(b'\x00', offset)
                    r_addr_full = realm_data[offset:end].decode('ascii'); offset = end + 1
                    
                    # Separar IP y Puerto
                    if ":" in r_addr_full:
                        r_host, r_port = r_addr_full.split(':')
                        r_port = int(r_port)
                    else:
                        r_host = r_addr_full
                        r_port = 8085 # Fallback
                        
                    r_pop = struct.unpack('<f', realm_data[offset:offset+4])[0]; offset += 4
                    r_chars = realm_data[offset]; offset += 1
                    r_cat = realm_data[offset]; offset += 1
                    r_id = realm_data[offset]; offset += 1
                    
                    realms.append({
                        "name": r_name,
                        "address": r_host,
                        "port": r_port,
                        "id": r_id,
                        "flags": r_flags
                    })
                    
                logger.info(f"Lista de reinos parseada: {[{'name': r['name'], 'id': r['id']} for r in realms]}")
            except Exception as e:
                logger.warning(f"Error parseando lista de reinos: {e}. Usando fallback.")
                # Fallback por si el formato varía ligeramente
                raw_str = realm_data.decode('ascii', errors='ignore')
                if "Thalassa" in raw_str:
                    realms.append({"name": "Thalassa", "address": self.host, "port": 8085, "id": 1})

            logger.info(f"[SESSIONKEY-AUTH] Longitud: {len(srp.K)}")
            logger.info(f"[SESSIONKEY-AUTH] HEX: {srp.K.hex(' ').upper()}")

            return {
                "status": "AUTH_PROOF_ACCEPTED",
                "details": f"Autenticación exitosa. {len(realms)} reinos encontrados.",
                "session_key": srp.K,
                "realms": realms
            }

        except Exception as e:
            return {"status": "AUTH_PARSE_ERROR", "details": str(e)}
        finally:
            writer.close()
            await writer.wait_closed()

    async def test_handshake(self, account: str) -> dict:
        """Mantiene compatibilidad con el botón de prueba anterior, pero ahora usa el flujo real."""
        # Para el hito 1 solo enviábamos el challenge. 
        # Aquí podemos simplemente llamar a una versión abreviada o usar el authenticate con pass vacía.
        return await self.authenticate(account, "dummy_pass")

    async def connect_and_authenticate(self, username: str, password: str) -> dict:
        return await self.authenticate(username, password)
