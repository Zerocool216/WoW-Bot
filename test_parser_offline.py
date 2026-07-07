#!/usr/bin/env python3
"""
Test offline del parser SMSG_MESSAGECHAT con hex dumps reales capturados.
"""
import struct

def parse_chat_fixed(payload: bytes) -> dict:
    """Parser corregido basado en análisis real de hex dumps."""
    try:
        if not payload or len(payload) < 29:
            return None

        offset = 0
        
        # [0]: msg_type (1 byte)
        msg_type = payload[0]
        offset = 1
        
        # [1-4]: lang (4 bytes)
        if offset + 4 > len(payload):
            return None
        lang = struct.unpack_from('<I', payload, offset)[0]
        offset += 4
        
        # [5-12]: sender_guid (8 bytes)
        if offset + 8 > len(payload):
            return None
        sender_guid = struct.unpack_from('<Q', payload, offset)[0]
        offset += 8
        
        # [13-20]: target_guid (8 bytes) ← ORDEN CORREGIDO
        if offset + 8 > len(payload):
            return None
        target_guid = struct.unpack_from('<Q', payload, offset)[0]
        offset += 8
        
        # [21-24]: unknown (4 bytes) ← AHORA DESPUÉS del target_guid
        if offset + 4 > len(payload):
            return None
        unknown = struct.unpack_from('<I', payload, offset)[0]
        offset += 4
        
        # [25-28]: message_length (4 bytes)
        if offset + 4 > len(payload):
            return None
        msg_len = struct.unpack_from('<I', payload, offset)[0]
        offset += 4
        
        # [29+]: message (variable length)
        if offset + msg_len > len(payload):
            return None
        msg = payload[offset:offset+msg_len].decode('utf-8', errors='ignore').rstrip('\x00')
        
        type_names = {1: "SAY", 4: "GUILD", 5: "OFFICER", 8: "YELL", 3: "WHISPER", 0: "SYSTEM", 17: "CHANNEL"}

        # Filtrar addons (tab separator)
        if '\t' in msg:
            return {
                "filtered": True,
                "type": type_names.get(msg_type, f"UNKNOWN_{msg_type}"),
                "sender_guid": sender_guid,
                "target_guid": target_guid,
                "message": msg,
                "lang": lang,
                "msg_type": msg_type
            }

        if msg_type in type_names:
            return {
                "type": type_names[msg_type],
                "sender_guid": sender_guid,
                "target_guid": target_guid,
                "message": msg,
                "lang": lang,
                "msg_type": msg_type
            }
        
    except Exception as e:
        return None
    
    return None

# Hex dumps capturados del bot
HEX_DUMPS = [
    "04FFFFFFFF01B00200000000000000000000000000000000002600000043726209532F206661333738632061366144732A3334653223252425242A2030426572796C0000",
    "04FFFFFFFF6102060000000000000000000000000000000000EF000000475359094A756C696965746124363134352432303236303632343037333524574124323636244452244124585858243830244E616572204D5650244A756C69696574612435313232373A333831372435333133323A302435313231303A3338303824303A302435313231343A333833322435303632303A302435313231313A333832332435303633393A333832362435303637303A333834352435303032313A333233312435303431343A302435303430323A302434373231343A302434373133313A302435303437303A313039392435303630333A333738392435303037303A333738392434393938313A30240000",
    "04FFFFFFFF01B00200000000000000000000000000000000001E000000437262095327206661333738632061366144732A3334653223252425240000",
    "04FFFFFFFF42F00C00000000000000000000000000000000000D00000044424D76342D4748094869210000",
    "04FFFFFFFF42F00C00000000000000000000000000000000000F00000041545209565245515F322E362E330000",
    "00000000000000000000000000000000000000000000000000340000007C6366666666303030305B4576656E74204D6573736167655D3A204C6F7320436F66726573204D6973746572696F736F737C720000",
    "04FFFFFFFF42F00C00000000000000000000000000000000003500000044424D76342D47560932303235313130323134333231380932303234303732303030303030300931302E312E313320616C7068610000",
    "04FFFFFFFF2B711200000000000000000000000000000000002B00000044424D76342D475609323032343130303931323030303009323032343130303930303030303009392E330000",
    "04FFFFFFFF01B002000000000000000000000000000000000031000000437262095329203765616231612062623844732A24732C373150616E63686F20456C204C6F636F3334653223252425240000",
    "00000000000000000000000000000000000000000000000000D00000007C4366666666303030305B5241494420494E464F5D207C6366663030666666664B6172617A68616E3A207C436666303066663030417474756D656E207468652048756E74736D616E207C636666303066666666646572726F7461646F20706F72206C61206865726D616E646164207C4366663030666630305761726272696E676572737C6366633030666666662E204A756761646F7265733A20372F31302020202050726F6772657369C3B36E3A20302F313120202020446574616C6C653A202E7261696420696E666F20313437330000",
]

EXPECTED_RESULTS = [
    "FILTERED",  # addon/GUILD message con TAB
    "FILTERED",  # addon/GUILD message con TAB
    "FILTERED",  # addon/GUILD message con TAB
    "FILTERED",  # addon/GUILD message con TAB
    "FILTERED",  # addon/GUILD message con TAB
    "PARSED",    # SYSTEM mensaje legítimo
    "FILTERED",  # addon/GUILD message con TAB
    "FILTERED",  # addon/GUILD message con TAB
    "FILTERED",  # addon/GUILD message con TAB
    "PARSED",    # SYSTEM mensaje legítimo
]

def test_parser():
    """Test el parser contra todos los hex dumps."""
    print("=" * 80)
    print("TEST DEL PARSER CORREGIDO")
    print("=" * 80)
    
    passed = 0
    failed = 0
    
    for i, (hex_str, expected) in enumerate(zip(HEX_DUMPS, EXPECTED_RESULTS), 1):
        payload = bytes.fromhex(hex_str)
        result = parse_chat_fixed(payload)

        if expected == "FILTERED":
            is_pass = result is not None and result.get("filtered") is True
        elif expected == "PARSED":
            is_pass = result is not None and result.get("filtered") is not True
        else:
            is_pass = False

        status = "✓ PASS" if is_pass else "✗ FAIL"
        if is_pass:
            passed += 1
        else:
            failed += 1

        print(f"\n[{i}] {status}")
        if expected == "PARSED":
            print(f"    Esperado mensaje parseado, obtenido: {result}")
        else:
            print(f"    Esperado mensaje filtrado, obtenido: {result}")
    
    print("\n" + "=" * 80)
    print(f"RESULTADOS: {passed} PASS, {failed} FAIL de {len(HEX_DUMPS)} total")
    print("=" * 80)
    
    return failed == 0

if __name__ == "__main__":
    success = test_parser()
    exit(0 if success else 1)
