response_hex = "030000130ed000001234000300080005000000"
response = bytes.fromhex(response_hex)

print("=== RDP Response Decoder ===")
print(f"Raw hex: {response_hex}")
print(f"Raw bytes: {response}")
print()

print("TPKT Header:")
print(f"  Version: {response[0]} (0x03 = TPKT)")
print(f"  Reserved: {response[1]}")
print(f"  Length: {(response[2] << 8) | response[3]} bytes")
print()

print("X.224 COTP:")
print(f"  Length Indicator: {response[4]} (LI = 0x{response[4]:02x})")
print(f"  PDU Type: {response[5]} (0x{response[5]:02x})")

if response[5] == 0xD0:
    print("  -> CC: Connection Confirm (Server Accept)")
    dst_ref = (response[6] << 8) | response[7]
    src_ref = (response[8] << 8) | response[9]
    print(f"  Destination Reference: 0x{dst_ref:04x}")
    print(f"  Source Reference: 0x{src_ref:04x}")
    print(f"  Class/Option: 0x{response[10]:02x}")
    print()
    print("[+] RDP SERVER IS RESPONDING CORRECTLY!")
    print("[+] This is a valid RDP connection acceptance")
    print("[+] You can now connect with: mstsc /v:localhost:17389")

elif response[5] == 0xE0:
    print("  -> CR: Connection Request (Not expected from server)")

elif response[5] == 0x80:
    print("  -> DR: Disconnect Request")

else:
    print(f"  -> Unknown PDU type")

print()
print("Remaining data:")
print(f"  {response[6:].hex()}")

if response[5] == 0xD0 and len(response) > 11:
    print()
    print("Variable part (RDP Negotiation):")
    pos = 11
    while pos < len(response):
        if pos + 3 >= len(response):
            break
        neg_type = response[pos]
        neg_flags = response[pos + 1]
        neg_length = (response[pos + 2] << 8) | response[pos + 3]
        print(
            f"  Type: 0x{neg_type:02x}, Flags: 0x{neg_flags:02x}, Length: {neg_length}"
        )
        pos += neg_length
