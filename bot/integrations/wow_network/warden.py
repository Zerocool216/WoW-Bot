import hashlib
import struct
import logging
from .crypto import RC4Crypto
from Crypto.Cipher import ARC4

logger = logging.getLogger("Warden")

class SHA1Randx:
    def __init__(self, session_key: bytes):
        key_half_size = len(session_key) // 2
        
        md = hashlib.sha1()
        md.update(session_key[:key_half_size])
        self.o1 = md.digest()
        
        md = hashlib.sha1()
        md.update(session_key[key_half_size:])
        self.o2 = md.digest()
        
        self.o0 = b''
        self.index = 0
        self._fill_up()
        
    def _fill_up(self):
        md = hashlib.sha1()
        md.update(self.o1)
        md.update(self.o0)
        md.update(self.o2)
        self.o0 = md.digest()
        self.index = 0
        
    def generate(self, size: int) -> bytes:
        res = bytearray()
        for _ in range(size):
            if self.index >= len(self.o0):
                self._fill_up()
            res.append(self.o0[self.index])
            self.index += 1
        return bytes(res)

class WardenHandler:
    """
    Manejador anti-cheat Warden para WoW 3.3.5a
    Basado en wowchat WardenHandler.scala
    """
    WARDEN_MODULE_LENGTH = 16
    
    # SMSG (Server to Client)
    SMSG_MODULE_USE = 0x00
    SMSG_MODULE_CACHE = 0x01
    SMSG_CHEAT_CHECKS_REQUEST = 0x02
    SMSG_MODULE_INITIALIZE = 0x03
    SMSG_MEM_CHECKS_REQUEST = 0x04
    SMSG_HASH_REQUEST = 0x05
    
    # CMSG (Client to Server)
    CMSG_MODULE_MISSING = 0x00
    CMSG_MODULE_OK = 0x01
    CMSG_CHEAT_CHECKS_RESULT = 0x02
    CMSG_MEM_CHECKS_RESULT = 0x03
    CMSG_HASH_RESULT = 0x04
    CMSG_MODULE_FAILED = 0x05
    
    def __init__(self, session_key: bytes):
        self.sha1_randx = SHA1Randx(session_key)
        self.client_crypt = ARC4.new(self.sha1_randx.generate(16))
        self.server_crypt = ARC4.new(self.sha1_randx.generate(16))
        self.module_crypt = None
        self.module_seed = b''
        
    def handle(self, payload: bytes) -> bytes:
        """
        Toma el payload de SMSG_WARDEN_DATA (0x02E6) y retorna 
        el payload a enviar en CMSG_WARDEN_DATA (0x02E7), o None.
        """
        if not payload: return None
        
        decrypted = self.server_crypt.decrypt(payload)
        warden_opcode = decrypted[0]
        data = decrypted[1:]
        
        logger.debug(f"[WARDEN] RECV Opcode 0x{warden_opcode:02X} | {decrypted.hex(' ').upper()}")
        
        if warden_opcode == self.SMSG_MODULE_USE:
            return self._handle_module_use(data)
        elif warden_opcode == self.SMSG_MODULE_CACHE:
            return self._handle_module_cache(data)
        elif warden_opcode == self.SMSG_CHEAT_CHECKS_REQUEST:
            return self._handle_cheat_checks_request(data)
        elif warden_opcode == self.SMSG_HASH_REQUEST:
            return self._handle_hash_request(data)
            
        return None
        
    def _handle_module_use(self, data: bytes) -> bytes:
        if len(data) < self.WARDEN_MODULE_LENGTH + 20:
            return None
        # Name is 16 bytes
        module_name = data[:self.WARDEN_MODULE_LENGTH]
        # Seed is 16 bytes
        self.module_seed = data[self.WARDEN_MODULE_LENGTH : self.WARDEN_MODULE_LENGTH + 16]
        # Length is 4 bytes
        module_length = struct.unpack('<I', data[self.WARDEN_MODULE_LENGTH+16 : self.WARDEN_MODULE_LENGTH+20])[0]
        
        self.module_crypt = ARC4.new(self.module_seed)
        logger.info(f"[WARDEN] MODULE_USE: {module_name.hex()} (len: {module_length})")
        
        # Enviar CMSG_MODULE_OK
        resp = bytes([self.CMSG_MODULE_OK])
        return self.client_crypt.encrypt(resp)
        
    def _handle_module_cache(self, data: bytes) -> bytes:
        # Aquí ignoramos la descarga real del módulo (que haría unzip etc)
        # y solo respondemos que está OK cuando termine.
        # Por simplicidad, si recibimos esto, respondemos OK
        # Ojo: esto es un hack. El servidor nos envía partes. Si asumimos que lo tenemos o no,
        # podríamos enviar MODULE_MISSING. Pero NaerZone a veces acepta MODULE_OK directo.
        logger.info("[WARDEN] MODULE_CACHE (Ignorando contenido, respondiendo OK)")
        resp = bytes([self.CMSG_MODULE_OK])
        return self.client_crypt.encrypt(resp)
        
    def _handle_cheat_checks_request(self, data: bytes) -> bytes:
        str_len = data[0] if data else 0
        str_array = data[1:1+str_len]
        
        # Filtrar hasta el null byte
        end_idx = str_array.find(b'\x00')
        if end_idx != -1:
            str_array = str_array[:end_idx]
            
        logger.info(f"[WARDEN] CHEAT_CHECKS_REQUEST string len={len(str_array)}")
        
        # Digest: SHA1(key + 0xFEEDFACE) + MD5(key)
        h1 = hashlib.sha1()
        h1.update(str_array)
        h1.update(struct.pack('<I', 0xFEEDFACE))
        
        h2 = hashlib.md5()
        h2.update(str_array)
        
        resp = bytes([self.CMSG_CHEAT_CHECKS_RESULT]) + h1.digest() + h2.digest()
        return self.client_crypt.encrypt(resp)
        
    def _handle_hash_request(self, data: bytes) -> bytes:
        logger.info("[WARDEN] HASH_REQUEST (Actualizando llaves crypto)")
        
        # Leer 4 enteros
        c_keys = list(struct.unpack('<IIII', data[:16]))
        s_keys = [0, 0, 0, 0]
        
        s_keys[0] = c_keys[0]
        c_keys[0] = c_keys[0] ^ 0xDEADBEEF
        
        sk1 = c_keys[1]
        c_keys[1] = (c_keys[1] - 0x35014542) & 0xFFFFFFFF
        
        sk2 = c_keys[2]
        c_keys[2] = (c_keys[2] + 0x05313F22) & 0xFFFFFFFF
        
        c_keys[3] = (c_keys[3] * 0x1337F00D) & 0xFFFFFFFF
        
        s_keys[1] = (sk1 - 0x6A028A84) & 0xFFFFFFFF
        s_keys[2] = (sk2 + 0x0A627E44) & 0xFFFFFFFF
        s_keys[3] = (0x1337F00D * c_keys[3]) & 0xFFFFFFFF
        
        client_key_bytes = struct.pack('<IIII', *c_keys)
        server_key_bytes = struct.pack('<IIII', *s_keys)
        
        # Hash correcto: SHA1(client_keys + server_keys)
        h = hashlib.sha1()
        h.update(client_key_bytes)
        h.update(server_key_bytes)
        
        resp = bytes([self.CMSG_HASH_RESULT]) + h.digest()
        encrypted = self.client_crypt.encrypt(resp)
        
        # Actualizar llaves
        self.client_crypt = ARC4.new(client_key_bytes)
        self.server_crypt = ARC4.new(server_key_bytes)
        
        return encrypted
