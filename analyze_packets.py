import struct

# Primer paquete fallido (tipo 04 = GUILD)
hex1 = "04FFFFFFFF01B00200000000000000000000000000000000002600000043726209532F206661333738632061366144732A3334653223252425242A2030426572796C0000"
payload1 = bytes.fromhex(hex1)

print("=" * 80)
print("PAQUETE 1 (tipo 04 - GUILD, len=%d):" % len(payload1))
print("=" * 80)
print("  [0]: msg_type = 0x%02X (%d)" % (payload1[0], payload1[0]))
print("  [1-4]: lang = 0x%08X" % struct.unpack_from('<I', payload1, 1)[0])
print("  [5-12]: sender_guid = 0x%016X" % struct.unpack_from('<Q', payload1, 5)[0])
print("  [13-20]: target_guid = 0x%016X" % struct.unpack_from('<Q', payload1, 13)[0])
print("  [21-24]: unk = 0x%08X" % struct.unpack_from('<I', payload1, 21)[0])
msg_len = struct.unpack_from('<I', payload1, 25)[0]
print("  [25-28]: msg_len = %d (0x%02X)" % (msg_len, msg_len))

msg_bytes = payload1[29:29+msg_len]
print("  [29-%d]: message HEX = %s" % (29+msg_len-1, msg_bytes.hex()))
print("  Message decoded: %s" % msg_bytes.decode('utf-8', errors='ignore'))
print("  Has TAB character (0x09): %s" % ('YES' if b'\x09' in msg_bytes else 'NO'))

print("\n" + "=" * 80)
print("PAQUETE 2 (tipo 00 - SYSTEM, len=%d):" % len(payload2 := bytes.fromhex("00000000000000000000000000000000000000000000000000340000007C6366666666303030305B4576656E74204D6573736167655D3A204C6F7320436F66726573204D6973746572696F736F737C720000")))
print("=" * 80)
print("  [0]: msg_type = 0x%02X (%d)" % (payload2[0], payload2[0]))
print("  [1-4]: lang = 0x%08X" % struct.unpack_from('<I', payload2, 1)[0])
print("  [5-12]: sender_guid = 0x%016X" % struct.unpack_from('<Q', payload2, 5)[0])
print("  [13-20]: target_guid = 0x%016X" % struct.unpack_from('<Q', payload2, 13)[0])
print("  [21-24]: unk = 0x%08X" % struct.unpack_from('<I', payload2, 21)[0])
msg_len2 = struct.unpack_from('<I', payload2, 25)[0]
print("  [25-28]: msg_len = %d (0x%02X)" % (msg_len2, msg_len2))

msg_bytes2 = payload2[29:29+msg_len2]
print("  [29-%d]: message decoded: %s" % (29+msg_len2-1, msg_bytes2.decode('utf-8', errors='ignore')[:60]))
