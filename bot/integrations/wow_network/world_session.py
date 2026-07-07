import asyncio
import struct
import hashlib
import os
import zlib
import logging
from typing import Tuple, List, AsyncGenerator, Optional
from .crypto import RC4Crypto
from .warden import WardenHandler
from .packets import Opcodes

logger = logging.getLogger("WorldSession")

def unpack_guid(payload: bytes, offset: int) -> Tuple[int, int]:
    """Desempaqueta un GUID comprimido de WotLK."""
    if offset >= len(payload):
        return 0, offset
    mask = payload[offset]
    offset += 1
    guid = 0
    for i in range(8):
        if mask & (1 << i):
            if offset < len(payload):
                guid |= (payload[offset] << (i * 8))
                offset += 1
    return guid, offset

class WorldSession:
    """
    Maneja el protocolo de red de WoW 3.3.5a (Build 12340).
    Flujo de producción limpio: Sin lecturas forenses ni duplicadas.
    """
    PENDING_CHAT_TTL = 30.0

    # Mapeo de IDs de comando de Guild (AzerothCore/TrinityCore 3.3.5a)
    GUILD_COMMAND_MAP = {
        0x00: "GUILD_CREATE",
        0x01: "GUILD_INVITE",
        0x02: "GUILD_JOIN",
        0x03: "GUILD_PROMOTE",
        0x04: "GUILD_DEMOTE",
        0x05: "GUILD_LEAVE",
        0x06: "GUILD_CHART",
        0x07: "GUILD_DISBAND",
        0x08: "GUILD_LEADER",
        0x09: "GUILD_MOTD",
        0x0A: "GUILD_ROSTER_UPDATE",
        0x0B: "GUILD_QUIT"
    }

    # Mapeo de Códigos de Resultado de Guild (AzerothCore/TrinityCore 3.3.5a)
    GUILD_RESULT_MAP = {
        0x00: "GUILD_CMD_RESULT_SUCCESS",
        0x01: "GUILD_CMD_RESULT_INTERNAL_ERROR",
        0x02: "GUILD_CMD_RESULT_NOT_IN_GUILD",
        0x03: "GUILD_CMD_RESULT_ALREADY_IN_GUILD",
        0x04: "GUILD_CMD_RESULT_ALREADY_IN_GUILD_S",
        0x05: "GUILD_CMD_RESULT_INVITED_TO_GUILD",
        0x06: "GUILD_CMD_RESULT_ALREADY_INVITED",
        0x07: "GUILD_CMD_RESULT_NOT_GUILDMASTER",
        0x08: "GUILD_CMD_RESULT_NOT_OFFICER",
        0x09: "GUILD_CMD_RESULT_NOT_PROMOTED",
        0x0A: "GUILD_CMD_RESULT_NOT_DEMOTED",
        0x0B: "GUILD_CMD_RESULT_RANK_TOO_HIGH",
        0x0C: "GUILD_CMD_RESULT_RANK_TOO_LOW",
        0x0D: "GUILD_CMD_RESULT_RANK_IN_USE",
        0x0E: "GUILD_CMD_RESULT_MEMBER_NOT_FOUND",
        0x0F: "GUILD_CMD_RESULT_NOT_AUTHORIZED",
        0x10: "GUILD_CMD_RESULT_NOT_ONLINE"
    }

    def __init__(self, host: str, port: int, account: str, sessionkey: bytes, realmid: int = 1):
        self.host = host
        self.port = port
        self.account = account
        self.sessionkey = sessionkey
        self.realmid = realmid
        
        self.name_cache = {}
        self.pending_chats = {}
        self.pending_chats_ts = {}
        
        self.reader = None
        self.writer = None
        self.crypto = None
        self.warden = None
        self.server_seed_bytes = None
        self.client_seed = int.from_bytes(os.urandom(4), 'little')
        self.connected = False
        self.chat_queue = asyncio.Queue()
        self.pingtask = None
        self._recv_task = None
        self.guild_motd = ""

        # Flujo de cambio de MOTD
        self._pending_gmotd = None
        self._last_gmotd_result = None

    async def sendpacket(self, opcode: int, payload: bytes):
        """Envía un paquete al World Server."""
        # WoW 3.3.5a C2S header: 2 bytes size + 4 bytes opcode = 6 bytes
        size_field = len(payload) + 4
        header = struct.pack('>H', size_field) + struct.pack('<I', opcode)
        
        # Omitir cifrado de cabecera para CMSG_AUTH_SESSION (0x01ED), el resto se cifra si RC4 está activo
        if self.crypto and opcode != Opcodes.CMSG_AUTH_SESSION:
            header = self.crypto.encrypt_header(header)
            
        self.writer.write(header + payload)
        await self.writer.drain()

    async def recvpacket(self, decrypt: bool = True) -> Tuple[int, bytes]:
        """Recibe un paquete con cabecera cifrada (S2C = 4 bytes)."""
        # 1. Leer header (4 bytes)
        buf_len = len(self.reader._buffer)
        try:
            header_raw = await asyncio.wait_for(self.reader.readexactly(4), timeout=5.0)
        except asyncio.TimeoutError:
            logger.error(f"[TIMEOUT] No se recibieron 4 bytes del servidor. Bytes en buffer: {buf_len}")
            if buf_len > 0:
                partial = bytes(self.reader._buffer)
                logger.error(f"Bytes parciales: {partial.hex(' ')}")
            raise
            
        if decrypt and self.crypto:
            header = self.crypto.decrypt_header(header_raw)
        else:
            header = header_raw
            
        # WotLK S2C Header: 2 bytes size (or 3 bytes if MSB=1), 2 bytes opcode
        is_large = (header[0] & 0x80) != 0
        
        if is_large:
            extra_byte_raw = await self.reader.readexactly(1)
            if decrypt and self.crypto:
                extra_byte = self.crypto.decrypt_header(extra_byte_raw)
            else:
                extra_byte = extra_byte_raw
                
            header_raw += extra_byte_raw
            header += extra_byte
            
            size = ((header[0] & 0x7F) << 16) | (header[1] << 8) | header[2]
            opcode = struct.unpack('<H', header[3:5])[0]
            payload_size = size - 2
        else:
            size = struct.unpack('>H', header[0:2])[0]
            opcode = struct.unpack('<H', header[2:4])[0]
            payload_size = size - 2

        logger.debug(f"[RAW-HEADER] decrypt={decrypt} raw={header_raw.hex(' ').upper()} parsed={header.hex(' ').upper()} (size={payload_size}, op=0x{opcode:04X})")
            
        # 2. Leer payload (size - 2)
        payload = b""
        if payload_size > 0:
            try:
                payload = await asyncio.wait_for(self.reader.readexactly(payload_size), timeout=3.0)
            except asyncio.TimeoutError:
                logger.error(f"[TIMEOUT PAYLOAD] Faltan bytes para el payload. Expected: {payload_size}")
                raise
            
        return opcode, payload

    async def pingloop(self):
        """Loop de mantenimiento (CMSG_PING) cada 30 segundos."""
        seq = 0
        while self.connected:
            try:
                # CMSG_PING (0x01DC): Sequence (4) + Latency (4)
                latency = 110  # Valor de latencia simulado realista
                payload = struct.pack('<II', seq, latency)
                await self.sendpacket(Opcodes.CMSG_PING, payload)
                logger.debug(f"[PING] Enviado CMSG_PING seq={seq}, latency={latency}")
                seq += 1
                await asyncio.sleep(30)
            except Exception as e:
                logger.error(f"Error en pingloop: {e}")
                break

    async def keepaliveloop(self):
        """Loop de mantenimiento alterno (CMSG_KEEP_ALIVE) cada 30 segundos, desfasado 15s."""
        await asyncio.sleep(15)
        while self.connected:
            try:
                # CMSG_KEEP_ALIVE (0x0407) no requiere payload
                await self.sendpacket(Opcodes.CMSG_KEEP_ALIVE, b'')
                logger.debug("[KEEPALIVE] Enviado CMSG_KEEP_ALIVE")
                await asyncio.sleep(30)
            except Exception as e:
                logger.error(f"Error en keepaliveloop: {e}")
                break

    async def listenchatevents(self) -> AsyncGenerator[dict, None]:
        """Loop de recepción principal. Despacha chat y pings."""
        self.pingtask = asyncio.create_task(self.pingloop())
        self.keepalivetask = asyncio.create_task(self.keepaliveloop())
        while self.connected:
            try:
                opcode, payload = await self.recvpacket(decrypt=True)
                
                if opcode == Opcodes.SMSG_PONG:
                    seq = struct.unpack('<I', payload)[0]
                    logger.debug(f"[PONG] Recibido para sequence {seq}")
                
                elif opcode == Opcodes.SMSG_MESSAGECHAT:
                    chat_data = self._parse_chat(payload)
                    if chat_data:
                        if chat_data.get("filtered"):
                            logger.debug("[DEBUG-NET] SMSG_MESSAGECHAT filtrado como addon y descartado sin error")
                            continue

                        guid = chat_data["sender_guid"]
                        logger.info(f"[DEBUG-NET] chat_data parseado con éxito: {chat_data}")
                        if guid == 0:
                            chat_data["sender"] = "Servidor"
                            logger.info("[DEBUG-NET] Enviando a listener: chat_data de Servidor")
                            yield chat_data
                        elif guid in self.name_cache:
                            chat_data["sender"] = self.name_cache[guid]
                            logger.info(f"[DEBUG-NET] Enviando a listener: chat_data de {chat_data['sender']}")
                            yield chat_data
                        else:
                            now = asyncio.get_event_loop().time()
                            if guid not in self.pending_chats:
                                self.pending_chats[guid] = []
                                self.pending_chats_ts[guid] = now
                                logger.info(f"[DEBUG-NET] Remitente {guid:016X} no está en cache. Añadiendo a pending_chats y solicitando CMSG_NAME_QUERY")
                                # Solicitar el nombre del jugador (CMSG_NAME_QUERY)
                                req = struct.pack('<Q', guid)
                                await self.sendpacket(Opcodes.CMSG_NAME_QUERY, req)

                            # Limitar a máximo 10 mensajes por GUID pendiente
                            if len(self.pending_chats[guid]) < 10:
                                self.pending_chats[guid].append(chat_data)

                            # TTL: si lleva más de 30s sin resolverse, descartar y limpiar
                            if now - self.pending_chats_ts.get(guid, now) > self.PENDING_CHAT_TTL:
                                logger.warning(f"PENDING-TTL: Descartando {len(self.pending_chats[guid])} mensajes de GUID {guid:016X} sin resolver")
                                del self.pending_chats[guid]
                                del self.pending_chats_ts[guid]
                    else:
                        logger.warning("[DEBUG-NET] Falló el parseo del paquete SMSG_MESSAGECHAT")
                            
                elif opcode == Opcodes.SMSG_GUILD_ROSTER:
                    try:
                        count = struct.unpack_from('<I', payload, 0)[0]
                        offset = 4

                        # MOTD (null-terminated string)
                        end_motd = payload.find(b'\x00', offset)
                        if end_motd != -1:
                            self.guild_motd = payload[offset:end_motd].decode('utf-8', errors='ignore')
                            logger.info(f"[ROSTER] Guild MOTD capturado: {self.guild_motd}")
                            offset = end_motd + 1

                        # ginfo (null-terminated string)
                        end_ginfo = payload.find(b'\x00', offset)
                        if end_ginfo != -1:
                            offset = end_ginfo + 1

                        # rankscount
                        if offset + 4 <= len(payload):
                            rankscount = struct.unpack_from('<I', payload, offset)[0]
                            offset += 4 + (rankscount * 4)  # 4 bytes por rango (flags)

                        for _ in range(count):
                            if offset + 9 > len(payload):
                                break

                            guid = struct.unpack_from('<Q', payload, offset)[0]
                            is_online = payload[offset + 8] != 0
                            offset += 9

                            # Name (null-terminated)
                            end_name = payload.find(b'\x00', offset)
                            if end_name == -1:
                                break
                            name = payload[offset:end_name].decode('utf-8', errors='ignore')
                            offset = end_name + 1

                            # Cache the name immediately!
                            if name:
                                self.name_cache[guid] = name

                            if offset + 11 > len(payload):
                                break
                            # rank_id(4) + level(1) + class(1) + gender(1) + zone_id(4) = 11 bytes
                            rank_id = struct.unpack_from('<I', payload, offset)[0]; offset += 4
                            level = payload[offset]; offset += 1
                            char_class = payload[offset]; offset += 1
                            offset += 1  # gender
                            zone_id = struct.unpack_from('<I', payload, offset)[0]; offset += 4

                            # last_logoff: solo si offline (float 4 bytes)
                            if not is_online:
                                if offset + 4 <= len(payload):
                                    offset += 4

                            # public_note (null-terminated, longitud variable)
                            end_pub = payload.find(b'\x00', offset)
                            if end_pub == -1:
                                break
                            offset = end_pub + 1

                            # officer_note (null-terminated, longitud variable)
                            end_off = payload.find(b'\x00', offset)
                            if end_off == -1:
                                break
                            offset = end_off + 1

                        logger.info(f"[ROSTER] Sincronizados {len(self.name_cache)} nombres de jugadores de la hermandad en caché.")
                    except Exception as e:
                        logger.error(f"Error parseando SMSG_GUILD_ROSTER: {e}", exc_info=True)
                            
                elif opcode == Opcodes.SMSG_NAME_QUERY_RESPONSE:
                    try:
                        q_guid, q_offset = unpack_guid(payload, 0)
                        if q_offset < len(payload):
                            name_known = payload[q_offset]
                            q_offset += 1
                            if name_known == 0 and q_offset < len(payload):
                                end_name = payload.find(b'\x00', q_offset)
                                if end_name != -1:
                                    p_name = payload[q_offset:end_name].decode('utf-8', errors='ignore')
                                    self.name_cache[q_guid] = p_name
                                    logger.info(f"[NAME_QUERY] Resuelto {q_guid:016X} -> {p_name}")
                                    
                                    # Enviar mensajes que estaban en cola esperando el nombre
                                    if q_guid in self.pending_chats:
                                        logger.info(f"[DEBUG-NET] Resolviendo {len(self.pending_chats[q_guid])} mensajes en cola para {p_name}")
                                        for c in self.pending_chats[q_guid]:
                                            c["sender"] = p_name
                                            logger.info(f"[DEBUG-NET] Enviando mensaje pendiente de {p_name} a listener: {c}")
                                            yield c
                                        del self.pending_chats[q_guid]
                                        if q_guid in self.pending_chats_ts:
                                            del self.pending_chats_ts[q_guid]
                                    else:
                                        logger.info(f"[DEBUG-NET] Ningún mensaje en cola para {p_name}")
                    except Exception as e:
                        logger.error(f"Error parseando SMSG_NAME_QUERY_RESPONSE: {e}")
                
                elif opcode == Opcodes.SMSG_GUILD_COMMAND_RESULT:
                    res = self.parse_guild_command_result(payload)
                    if res:
                        cmd = res.get("command")
                        result = res.get("result")
                        extra_str = res.get("string")
                        
                        cmd_name = self.GUILD_COMMAND_MAP.get(cmd, f"DESCONOCIDO_{cmd}")
                        res_name = self.GUILD_RESULT_MAP.get(result, f"DESCONOCIDO_{result}")
                        
                        logger.info(f"[GUILD-CMD-RESULT] cmd={cmd} ({cmd_name}) result={result} ({res_name}) msg={extra_str!r}")
                        
                        # Correlacionar si el comando es de MOTD
                        if cmd in [8, 9] or self._pending_gmotd is not None:
                            self._last_gmotd_result = res
                            if result == 0:
                                logger.info(f"[GUILD-MOTD] ¡Cambio de MOTD exitoso! Confirmado por el servidor para: '{self._pending_gmotd}'")
                                if self._pending_gmotd:
                                    self.guild_motd = self._pending_gmotd
                            else:
                                logger.warning(f"[GUILD-MOTD] Cambio de MOTD RECHAZADO por el servidor. Razón: {res_name} ({result})")
                            self._pending_gmotd = None

                elif opcode == Opcodes.SMSG_GUILD_EVENT:
                    try:
                        if len(payload) >= 2:
                            event_type = payload[0]
                            # GE_MOTD is 2 in WotLK
                            if event_type == 2:
                                offset = 2
                                end_motd = payload.find(b'\x00', offset)
                                if end_motd != -1:
                                    self.guild_motd = payload[offset:end_motd].decode('utf-8', errors='ignore')
                                    logger.info(f"[GUILD-EVENT] MOTD detectado y actualizado en vivo: {self.guild_motd}")
                    except Exception as e:
                        logger.error(f"Error parseando SMSG_GUILD_EVENT: {e}")

                elif opcode == Opcodes.SMSG_NOTIFICATION:
                    msg = payload.decode('utf-8', errors='ignore')
                    logger.debug(f"[NOTIF] {msg}")

                elif opcode == Opcodes.SMSG_WARDEN_DATA:
                    if self.warden:
                        resp = self.warden.handle(payload)
                        if resp:
                            await self.sendpacket(Opcodes.CMSG_WARDEN_DATA, resp)  # CMSG_WARDEN_DATA

                elif opcode == Opcodes.SMSG_TIME_SYNC_REQ:
                    counter = struct.unpack('<I', payload[:4])[0] if len(payload) >= 4 else 0
                    resp = struct.pack('<II', counter, 0)
                    await self.sendpacket(Opcodes.CMSG_TIME_SYNC_RESP, resp)  # CMSG_TIME_SYNC_RESP
                    logger.debug(f"[LOOP] TIME_SYNC_REQ counter={counter} respondido")

            except asyncio.IncompleteReadError:
                logger.warning("Conexión cerrada por el servidor.")
                break
            except Exception as e:
                logger.error(f"Error en recv_loop: {e}")
                await asyncio.sleep(0.1)

    def _parse_chat(self, payload: bytes) -> dict:
        """Parser de SMSG_MESSAGECHAT para WotLK 3.3.5a - Estructura verificada por Hex Dump."""
        try:
            if not payload or len(payload) < 29:
                return None

            offset = 0
            msg_type = payload[0]
            offset = 1

            lang = struct.unpack_from('<I', payload, offset)[0]
            offset += 4

            sender_guid = struct.unpack_from('<Q', payload, offset)[0]
            offset += 8

            flags = struct.unpack_from('<I', payload, offset)[0]
            offset += 4

            target_guid = struct.unpack_from('<Q', payload, offset)[0]
            offset += 8

            msg_len = struct.unpack_from('<I', payload, offset)[0]
            offset += 4

            if offset + msg_len > len(payload):
                return None
                
            msg = payload[offset:offset+msg_len].decode('utf-8', errors='ignore').rstrip('\x00')

            type_names = {
                0: "SYSTEM",
                1: "SAY",
                2: "PARTY",
                3: "RAID",
                4: "GUILD",
                5: "OFFICER",
                6: "YELL",
                7: "WHISPER",
                17: "CHANNEL"
            }

            if '\t' in msg:
                return {
                    "filtered": True,
                    "sender_guid": sender_guid,
                    "message": msg,
                    "type": type_names.get(msg_type, f"UNKNOWN_{msg_type}")
                }

            if msg_type in type_names:
                return {
                    "type": type_names[msg_type],
                    "sender_guid": sender_guid,
                    "message": msg,
                    "channel_name": ""
                }
        except Exception as e:
            logger.error(f"[DEBUG-NET] Error parseando chat: {e}", exc_info=True)
        return None

    def parse_guild_command_result(self, payload: bytes) -> dict:
        """Parsea el resultado de un comando de Guild (SMSG_GUILD_COMMAND_RESULT)."""
        try:
            cmd = struct.unpack_from('<I', payload, 0)[0]
            end_str = payload.find(b'\x00', 4)
            result_str = payload[4:end_str].decode('utf-8', errors='ignore') if end_str != -1 else ""
            result_offset = (end_str + 1) if end_str != -1 else 4
            result = struct.unpack_from('<I', payload, result_offset)[0] if result_offset + 4 <= len(payload) else 0xFF
            return {
                "command": cmd,
                "result": result,
                "string": result_str
            }
        except Exception as e:
            logger.error(f"[GUILD-CMD-RESULT] Error parseando payload: {e}")
            return {}

    def get_last_gmotd_status(self) -> Optional[dict]:
        """
        Devuelve el último resultado conocido de un intento de cambio de GMOTD.
        """
        return self._last_gmotd_result

    async def connect(self) -> bool:
        """Fase 1: Conexión TCP."""
        logger.info(f"[WorldSession] Conectando a {self.host}:{self.port}...")
        try:
            self.reader, self.writer = await asyncio.wait_for(
                asyncio.open_connection(self.host, self.port), timeout=5.0
            )
            self.connected = True
            return True
        except Exception as e:
            logger.error(f"Error de conexión World: {e}")
            return False

    async def recv_auth_challenge(self) -> bool:
        """Fase 2: Recibir Challenge (Plano)."""
        try:
            opcode, payload = await self.recvpacket(decrypt=False)
            if opcode != Opcodes.SMSG_AUTH_CHALLENGE:
                logger.error(f"Esperado 0x{Opcodes.SMSG_AUTH_CHALLENGE:04X}, recibido 0x{opcode:04X}")
                return False
            
            # Estructura 3.3.5a: one (4) | seed (4) | seed1 (32)
            self.server_seed_bytes = payload[4:8]
            logger.info(f"[CHALLENGE] server_seed: {self.server_seed_bytes.hex(' ').upper()}")
            return True
        except Exception as e:
            logger.error(f"Error en recv_auth_challenge: {e}")
            return False

    async def send_auth_session(self):
        """Fase 3: Enviar Sesión (Plano)."""
        acc_upper = self.account.upper().strip()
        acc_bytes = acc_upper.encode('ascii')
        build = 12340

        # Digest-V3: SHA1(Acc | 0x00000000 | ClientSeed | ServerSeed | SessionKey)
        h = hashlib.sha1()
        h.update(acc_bytes)
        h.update(struct.pack('<I', 0)) # Faltaba este padding de 4 bytes en el hash
        h.update(struct.pack('<I', self.client_seed))
        h.update(self.server_seed_bytes)
        h.update(self.sessionkey)
        digest = h.digest()
        logger.info(f"[DIGEST-V3] Resultado: {digest.hex(' ').upper()}")

        # Mimetizando el payload estándar de 3.3.5a
        addon_block = self._build_addon_info()
        payload = b''
        payload += struct.pack('<I', build)
        payload += struct.pack('<I', 0)
        payload += acc_bytes + b'\x00'
        payload += struct.pack('<I', 0)
        payload += struct.pack('<I', self.client_seed)
        payload += struct.pack('<I', 0)
        payload += struct.pack('<I', 0)
        payload += struct.pack('<I', self.realmid)
        payload += struct.pack('<Q', 0) # dosResponse
        payload += digest
        payload += addon_block

        # Construir header manualmente para loguear los bytes exactos (6 bytes: 2 size + 4 opcode)
        size_field = len(payload) + 4
        raw_header = struct.pack('>H', size_field) + struct.pack('<I', Opcodes.CMSG_AUTH_SESSION)
        raw_packet = raw_header + payload

        logger.info(f"[AUTH-RAW] Header (6b): {raw_header.hex(' ').upper()}")
        logger.info(f"[AUTH-RAW] Payload primeros 40b: {payload[:40].hex(' ').upper()}")
        logger.info(f"[AUTH-RAW] Total bytes enviados: {len(raw_packet)}")
        logger.info(f"[AUTH-RAW] AddonBlock (primeros 16b): {addon_block[:16].hex(' ').upper()}")

        # Inicializar descifrado de cabeceras RC4 (como wowchat)
        # Esto prepara el descifrador para SMSG_AUTH_RESPONSE y paquetes subsiguientes
        self.crypto = RC4Crypto(self.sessionkey)

        # Enviar sesión (excluida de cifrado por ser opcode 0x01ED)
        await self.sendpacket(Opcodes.CMSG_AUTH_SESSION, payload)
        logger.info("[SEND] CMSG_AUTH_SESSION enviado")

    async def recv_auth_response(self) -> bool:
        """Fase 4: Recibir SMSG_AUTH_RESPONSE (cifrado con RC4).
        
        En WotLK 3.3.5a el servidor puede enviar SMSG_ADDON_INFO (0x02E6)
        ANTES del SMSG_AUTH_RESPONSE (0x01EE). Hay que consumir todos los
        paquetes intermedios hasta encontrar el AUTH_RESPONSE.
        """
        try:
            # Inicializar manejador Warden con la llave de sesión AHORA, para no perder paquetes
            self.warden = WardenHandler(self.sessionkey)

            # Loop para consumir paquetes hasta encontrar SMSG_AUTH_RESPONSE
            for _ in range(10):  # máximo 10 intentos
                opcode, payload = await self.recvpacket(decrypt=True)
                logger.debug(f"[AUTH-LOOP] Opcode: 0x{opcode:04X} ({len(payload)} bytes payload)")

                if opcode == Opcodes.SMSG_AUTH_RESPONSE:  # SMSG_AUTH_RESPONSE
                    if not payload or payload[0] != 0x0C:
                        error_code = payload[0] if payload else 0xFF
                        logger.error(f"AUTH_REJECT: código 0x{error_code:02X}")
                        return False
                    logger.info("✓ AUTH_OK — Sesión de mundo establecida.")
                    self.connected = True
                    return True

                elif opcode == Opcodes.SMSG_WARDEN_DATA:  # SMSG_WARDEN_DATA
                    logger.info("[AUTH-LOOP] Procesando SMSG_WARDEN_DATA preliminar...")
                    if self.warden:
                        resp = self.warden.handle(payload)
                        if resp:
                            await self.sendpacket(Opcodes.CMSG_WARDEN_DATA, resp)  # CMSG_WARDEN_DATA
                    continue

                elif opcode == Opcodes.SMSG_AUTH_WAIT_QUEUE:  # SMSG_AUTH_WAIT_QUEUE
                    pos = struct.unpack('<I', payload[:4])[0] if len(payload) >= 4 else 0
                    logger.info(f"[AUTH-LOOP] En cola, posición: {pos}. Esperando...")
                    continue

                else:
                    logger.warning(f"[AUTH-LOOP] Paquete inesperado 0x{opcode:04X}, descartando...")
                    continue

            logger.error("AUTH_RESPONSE no recibido después de 10 paquetes.")
            return False

        except Exception as e:
            logger.error(f"Error en recv_auth_response: {e}")
            return False

    async def get_char_list(self) -> List[dict]:
        """Fase 5: Obtener lista de personajes."""
        if not self.connected: return []
        try:
            await self.sendpacket(Opcodes.CMSG_CHAR_ENUM, b"")
            logger.info("[SEND] CMSG_CHAR_ENUM enviado")

            # Loop: consumir paquetes hasta encontrar SMSG_CHAR_ENUM (0x003B)
            for _ in range(15):
                opcode, payload = await self.recvpacket(decrypt=True)
                logger.debug(f"[CHAR-LOOP] Opcode: 0x{opcode:04X} ({len(payload)}b)")
                if opcode == Opcodes.SMSG_CHAR_ENUM:  # SMSG_CHAR_ENUM
                    return self._parse_chars(payload)
                elif opcode == Opcodes.SMSG_WARDEN_DATA:  # SMSG_WARDEN_DATA
                    if self.warden:
                        resp = self.warden.handle(payload)
                        if resp:
                            await self.sendpacket(Opcodes.CMSG_WARDEN_DATA, resp)  # CMSG_WARDEN_DATA
                # ignorar cualquier otro paquete previo

            logger.error("SMSG_CHAR_ENUM no recibido.")
            return []
        except Exception as e:
            logger.error(f"Error en get_char_list: {e}")
            return []

    async def login_character(self, guid: int) -> bool:
        """Fase 6: Entrar al mundo con el personaje."""
        if not self.connected: return False
        try:
            payload = struct.pack('<Q', guid)
            await self.sendpacket(Opcodes.CMSG_PLAYER_LOGIN, payload)
            logger.info(f"[SEND] CMSG_PLAYER_LOGIN enviado (GUID: {guid:016X})")

            # Loop ilimitado: el server puede enviar cientos de paquetes de object update
            # antes de enviar el SMSG_LOGIN_VERIFY_WORLD (0x03FA)
            while True:
                try:
                    opcode, payload = await asyncio.wait_for(
                        self.recvpacket(decrypt=True), timeout=10.0
                    )
                except asyncio.TimeoutError:
                    logger.error("[LOGIN] Timeout esperando LOGIN_VERIFY_WORLD")
                    return False

                logger.debug(f"[LOGIN-LOOP] Opcode: 0x{opcode:04X} ({len(payload)}b)")

                if opcode == Opcodes.SMSG_LOGIN_VERIFY_WORLD:  # SMSG_LOGIN_VERIFY_WORLD (WotLK 3.3.5a = 0x0236)
                    map_id, x, y, z, o = struct.unpack('<Iffff', payload[:20])
                    logger.info(f"✓ EN EL MUNDO — Map:{map_id} X:{x:.1f} Y:{y:.1f} Z:{z:.1f}")
                    return True

                if opcode == Opcodes.SMSG_TIME_SYNC_REQ:  # SMSG_TIME_SYNC_REQ — WotLK requiere respuesta
                    counter = struct.unpack('<I', payload[:4])[0] if len(payload) >= 4 else 0
                    resp = struct.pack('<II', counter, 0)  # counter + client_ticks
                    await self.sendpacket(Opcodes.CMSG_TIME_SYNC_RESP, resp)  # CMSG_TIME_SYNC_RESP
                    logger.info(f"[LOGIN] SMSG_TIME_SYNC_REQ counter={counter} -> respondido")
                    continue

                if opcode == Opcodes.SMSG_WARDEN_DATA:  # SMSG_WARDEN_DATA
                    if self.warden:
                        resp = self.warden.handle(payload)
                        if resp:
                            await self.sendpacket(Opcodes.CMSG_WARDEN_DATA, resp)  # CMSG_WARDEN_DATA
                    continue

                if opcode == Opcodes.SMSG_CHARACTER_LOGIN_FAILED:  # SMSG_CHARACTER_LOGIN_FAILED
                    code = payload[0] if payload else 0xFF
                    logger.error(f"[LOGIN] SMSG_CHARACTER_LOGIN_FAILED: 0x{code:02X}")
                    return False
        except Exception as e:
            logger.error(f"Error en login_character: {e}")
            return False

    async def send_chat_message(self, message: str, chat_type: int = 1, lang: int = 0) -> bool:
        """Envía mensaje al mundo WoW vía CMSG_MESSAGECHAT (0x0095)."""
        if not self.connected: return False
        try:
            msg_bytes = message.encode('utf-8') + b'\x00'
            # Estructura: type(4) | lang(4) | [target(string) si whisper] | message(string)
            # Para SAY/GUILD/YELL, no hay target.
            payload = struct.pack('<II', chat_type, lang) + msg_bytes
            await self.sendpacket(Opcodes.CMSG_MESSAGECHAT, payload)
            logger.info(f"[CHAT→WoW] [{chat_type}] {message}")
            return True
        except Exception as e:
            logger.error(f"Error enviando mensaje chat: {e}")
            return False

    async def send_guild_motd(self, new_motd: str) -> bool:
        """Cambia el MOTD de la hermandad vía CMSG_GUILD_MOTD.
        
        Opcode WotLK 3.3.5a build 12340: 0x008E (Opcodes.CMSG_GUILD_MOTD)
        Requiere que el personaje sea Oficial o GM con permisos de editar MOTD.
        """
        if not self.connected:
            logger.warning("[GUILD-MOTD] Intento de cambiar MOTD sin conexión activa.")
            return False
        try:
            self._pending_gmotd = new_motd
            self._last_gmotd_result = None
            payload = new_motd.encode('utf-8') + b'\x00'
            await self.sendpacket(Opcodes.CMSG_GUILD_MOTD, payload)
            logger.info(f"[GUILD-MOTD] Enviando CMSG_GUILD_MOTD: '{new_motd}'")
            return True
        except Exception as e:
            logger.error(f"[GUILD-MOTD] Error enviando CMSG_GUILD_MOTD: {e}")
            return False

    async def refresh_guild_roster(self) -> None:
        """Solicita SMSG_GUILD_ROSTER al servidor para refrescar el MOTD cacheado."""
        if not self.connected:
            return
        try:
            await self.sendpacket(Opcodes.CMSG_GUILD_ROSTER, b'')  # CMSG_GUILD_ROSTER
            logger.info("[GUILD-MOTD] Solicitado CMSG_GUILD_ROSTER para refrescar MOTD")
        except Exception as e:
            logger.error(f"Error solicitando CMSG_GUILD_ROSTER: {e}")

    def _parse_chars(self, payload) -> List[dict]:
        """Parser de SMSG_CHAR_ENUM para WotLK 3.3.5a.
        Estructura por personaje (basada en GamePacketHandlerWotLK.scala):
          guid(8) | name(str+\x00) | race(1) | class(1) | gender(1) |
          skin(1) | face(1) | hairStyle(1) | hairColor(1) | facialHair(1) |
          level(1) | zone(4) | map(4) | x(4) | y(4) | z(4) |
          guildGuid(4) | charFlags(4) | customizeFlags(4) | firstLogin(1) |
          petInfo(12) | equipment(19*9=171) | bagDisplay(4*9=36)
        """
        if not payload: return []
        count = payload[0]
        chars = []
        offset = 1
        for i in range(count):
            try:
                # GUID (8 bytes)
                guid = struct.unpack('<Q', payload[offset:offset+8])[0]
                offset += 8
                # Name (null-terminated string)
                end_name = payload.find(b'\x00', offset)
                name = payload[offset:end_name].decode('utf-8', errors='ignore')
                offset = end_name + 1
                # race(1) class(1) gender(1) skin(1) face(1) hairStyle(1) hairColor(1) facialHair(1)
                race = payload[offset]
                cls  = payload[offset + 1]
                offset += 8
                # level(1)
                level = payload[offset]
                offset += 1
                # zone(4) map(4) x(4)y(4)z(4)
                offset += 4 + 4 + 12
                # guildGuid(4)
                offset += 4
                # charFlags(4) customizeFlags(4) firstLogin(1)
                offset += 4 + 4 + 1
                # petInfo: id(4) level(4) family(4) = 12 bytes
                offset += 12
                # equipment: 19 slots * 9 bytes = 171 bytes
                offset += 19 * 9
                # bags: 4 * 9 bytes = 36 bytes
                offset += 4 * 9
                logger.info(f"[CHAR] {name} Lvl{level} (guid={guid:016X})")
                chars.append({"name": name, "level": level, "race": race, "class": cls, "guid": guid})
            except Exception as e:
                logger.warning(f"[CHAR-PARSE] Error en personaje {i}: {e}")
                break
        return chars

    def _build_addon_info(self) -> bytes:
        # Bloque de Addons HARDCODED copiado byte a byte desde wowchat (GamePacketHandlerWotLK.scala)
        # Esto emula perfectamente un cliente Mac legítimo y evita kicks por Warden/Addons
        return bytes([
            0x9E, 0x02, 0x00, 0x00, 0x78, 0x9C, 0x75, 0xD2, 0xC1, 0x6A, 0xC3, 0x30, 0x0C, 0xC6, 0x71, 0xEF,
            0x29, 0x76, 0xE9, 0x9B, 0xEC, 0xB4, 0xB4, 0x50, 0xC2, 0xEA, 0xCB, 0xE2, 0x9E, 0x8B, 0x62, 0x7F,
            0x4B, 0x44, 0x6C, 0x39, 0x38, 0x4E, 0xB7, 0xF6, 0x3D, 0xFA, 0xBE, 0x65, 0xB7, 0x0D, 0x94, 0xF3,
            0x4F, 0x48, 0xF0, 0x47, 0xAF, 0xC6, 0x98, 0x26, 0xF2, 0xFD, 0x4E, 0x25, 0x5C, 0xDE, 0xFD, 0xC8,
            0xB8, 0x22, 0x41, 0xEA, 0xB9, 0x35, 0x2F, 0xE9, 0x7B, 0x77, 0x32, 0xFF, 0xBC, 0x40, 0x48, 0x97,
            0xD5, 0x57, 0xCE, 0xA2, 0x5A, 0x43, 0xA5, 0x47, 0x59, 0xC6, 0x3C, 0x6F, 0x70, 0xAD, 0x11, 0x5F,
            0x8C, 0x18, 0x2C, 0x0B, 0x27, 0x9A, 0xB5, 0x21, 0x96, 0xC0, 0x32, 0xA8, 0x0B, 0xF6, 0x14, 0x21,
            0x81, 0x8A, 0x46, 0x39, 0xF5, 0x54, 0x4F, 0x79, 0xD8, 0x34, 0x87, 0x9F, 0xAA, 0xE0, 0x01, 0xFD,
            0x3A, 0xB8, 0x9C, 0xE3, 0xA2, 0xE0, 0xD1, 0xEE, 0x47, 0xD2, 0x0B, 0x1D, 0x6D, 0xB7, 0x96, 0x2B,
            0x6E, 0x3A, 0xC6, 0xDB, 0x3C, 0xEA, 0xB2, 0x72, 0x0C, 0x0D, 0xC9, 0xA4, 0x6A, 0x2B, 0xCB, 0x0C,
            0xAF, 0x1F, 0x6C, 0x2B, 0x52, 0x97, 0xFD, 0x84, 0xBA, 0x95, 0xC7, 0x92, 0x2F, 0x59, 0x95, 0x4F,
            0xE2, 0xA0, 0x82, 0xFB, 0x2D, 0xAA, 0xDF, 0x73, 0x9C, 0x60, 0x49, 0x68, 0x80, 0xD6, 0xDB, 0xE5,
            0x09, 0xFA, 0x13, 0xB8, 0x42, 0x01, 0xDD, 0xC4, 0x31, 0x6E, 0x31, 0x0B, 0xCA, 0x5F, 0x7B, 0x7B,
            0x1C, 0x3E, 0x9E, 0xE1, 0x93, 0xC8, 0x8D
        ])

    async def join_channel(self, channel_name: str, password: str = ""):
        """Se une a un canal público (ej: Taberna, BuscarGrupo)."""
        # CMSG_JOIN_CHANNEL = 0x0097
        # Payload WotLK 3.3.5a: channel_id(4) + unk1(1) + unk2(1) + name(null-term) + pass(null-term)
        payload = struct.pack('<IBB', 0, 0, 0)
        payload += channel_name.encode('utf-8') + b'\x00' + password.encode('utf-8') + b'\x00'
        await self.sendpacket(Opcodes.CMSG_JOIN_CHANNEL, payload)
        logger.info(f"Petición para unirse al canal '{channel_name}' enviada.")

    async def disconnect(self):
        self.connected = False
        if self.writer:
            self.writer.close()
            await self.writer.wait_closed()
