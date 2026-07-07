import hashlib
import os
import struct
import logging
from Crypto.Cipher import ARC4

logger = logging.getLogger("Crypto")

class AuthPackets:
    """
    Construcción y deconstrucción de paquetes binarios para el Auth Server.
    """
    @staticmethod
    def build_logon_challenge(account: str) -> bytes:
        account_bytes = account.upper().encode('ascii')
        size = 30 + len(account_bytes)
        fmt = f'<BBH4sBBBH4s4s4sIIB{len(account_bytes)}s'
        return struct.pack(
            fmt, 0x00, 0x00, size, b'WoW\0', 3, 3, 5, 12340,
            b'68x\0', b'niW\0', b'SUne', 0, 0, len(account_bytes), account_bytes
        )

    @staticmethod
    def build_logon_proof(A: bytes, M1: bytes) -> bytes:
        fmt = '<B 32s 20s 20s B B'
        return struct.pack(fmt, 0x01, A, M1, b'\x00' * 20, 0, 0)

class SRP6:
    """
    Implementación real de SRP6a para WoW 3.3.5a.
    """
    def __init__(self, username: str, password: str):
        self.username = username.upper()
        self.password = password.upper()
        self.g = 7
        self.N = int('894B645E89E1535BBDAD5B8B290650530801B18EBFBF5E8FAB3C82872A3E9BB7', 16)
        self.k = 3
        self.a = int.from_bytes(os.urandom(32), 'little')
        self.A = pow(self.g, self.a, self.N)
        self.K = None

    def get_A(self, g: int = 7, N: int = None) -> bytes:
        if g: self.g = g
        if N: self.N = N
        self.A = pow(self.g, self.a, self.N)
        return self.A.to_bytes(32, 'little')

    def calculate_M1(self, B_bytes: bytes, salt_bytes: bytes, g_bytes: bytes = None, N_bytes: bytes = None) -> bytes:
        B = int.from_bytes(B_bytes, 'little')
        
        # 1. x = H(s, H(u, ":", p))
        h_up = hashlib.sha1(f"{self.username}:{self.password}".encode()).digest()
        x = int.from_bytes(hashlib.sha1(salt_bytes + h_up).digest(), 'little')
        
        # 2. u = H(A, B)
        A_bytes = self.A.to_bytes(32, 'little')
        u = int.from_bytes(hashlib.sha1(A_bytes + B_bytes).digest(), 'little')
        
        # 3. S = (B - k*g^x)^(a + u*x) % N
        S_int = pow((B - self.k * pow(self.g, x, self.N)) % self.N, (self.a + u * x), self.N)
        S_bytes = S_int.to_bytes(32, 'little')
        
        # 4. K = Interleave SHA1(S) (40 bytes)
        S_even = bytes([S_bytes[i] for i in range(0, 32, 2)])
        S_odd = bytes([S_bytes[i] for i in range(1, 32, 2)])
        K1 = hashlib.sha1(S_even).digest()
        K2 = hashlib.sha1(S_odd).digest()
        self.K = bytes([val for pair in zip(K1, K2) for val in pair])
        
        # 5. M1 = H(H(N) ^ H(g), H(I), s, A, B, K)
        hN = hashlib.sha1(self.N.to_bytes(32, 'little')).digest()
        hg = hashlib.sha1(self.g.to_bytes(1, 'little')).digest()
        xor_ng = bytes(a ^ b for a, b in zip(hN, hg))
        hash_u = hashlib.sha1(self.username.encode()).digest()
        
        logger.info(f"[SRP6] XorNg:    {xor_ng.hex().upper()}")
        logger.info(f"[SRP6] hash_U:   {hash_u.hex().upper()}")
        logger.info(f"[SRP6] salt:     {salt_bytes.hex().upper()}")
        logger.info(f"[SRP6] A:        {A_bytes.hex().upper()}")
        logger.info(f"[SRP6] B:        {B_bytes.hex().upper()}")
        logger.info(f"[SRP6] K:        {self.K.hex().upper()} (Len: {len(self.K)})")
        
        h = hashlib.sha1()
        h.update(xor_ng)
        h.update(hash_u)
        h.update(salt_bytes)
        h.update(A_bytes)
        h.update(B_bytes)
        h.update(self.K)
        M1 = h.digest()
        
        logger.info(f"[SRP6] M1:       {M1.hex().upper()}")
        return M1

class RC4Crypto:
    """
    Criptografía de cabeceras WoW 3.3.5a con derivación HMAC-SHA1 y Drop 1024.
    """
    # Seeds correctas para WoW WotLK 3.3.5a (build 12340)
    # Fuente: wowchat GameHeaderCryptWotLK.scala
    _C_S_SEED = bytes([  # clientHmacSeed: usado para cifrar C→S
        0xC2, 0xB3, 0x72, 0x3C, 0xC6, 0xAE, 0xD9, 0xB5,
        0x34, 0x3C, 0x53, 0xEE, 0x2F, 0x43, 0x67, 0xCE
    ])
    _S_C_SEED = bytes([  # serverHmacSeed: usado para descifrar S→C
        0xCC, 0x98, 0xAE, 0x04, 0xE8, 0x97, 0xEA, 0xCA,
        0x12, 0xDD, 0xC0, 0x93, 0x42, 0x91, 0x53, 0x57
    ])

    def __init__(self, session_key: bytes):
        import hmac, hashlib
        send_key = hmac.new(self._C_S_SEED, session_key, hashlib.sha1).digest()
        recv_key = hmac.new(self._S_C_SEED, session_key, hashlib.sha1).digest()
        
        self._send = ARC4.new(send_key)
        self._recv = ARC4.new(recv_key)
        
        # Drop 1024 bytes (estándar WoW)
        _drop = b'\x00' * 1024
        self._send.encrypt(_drop)
        self._recv.decrypt(_drop)

    def encrypt_header(self, data: bytes) -> bytes:
        """Cifra cabecera de 6 bytes (C2S)."""
        return self._send.encrypt(data)

    def decrypt_header(self, data: bytes) -> bytes:
        """Descifra cabecera de 4 bytes (S2C)."""
        return self._recv.decrypt(data)

