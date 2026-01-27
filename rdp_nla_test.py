import socket
import struct

def build_rdp_cr(nla_enabled=True):
    cookie = b"Cookie: mstshash=test\r\n"
    
    if nla_enabled:
        neg_req = bytes([0x01, 0x00, 0x08, 0x00, 0x03, 0x00, 0x00, 0x00])
    else:
        neg_req = bytes([0x01, 0x00, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00])
    
    x224_data = bytes([0xe0, 0x00, 0x00, 0x00, 0x00, 0x00]) + cookie + neg_req
    x224_header = bytes([len(x224_data)])
    tpkt = bytes([0x03, 0x00]) + struct.pack(">H", 4 + 1 + len(x224_data)) + x224_header + x224_data
    return tpkt

def test_rdp_auth(port, nla):
    mode = "NLA" if nla else "NO-NLA"
    print(f"[*] Testing RDP on :{port} with {mode}...", end=" ", flush=True)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect(("localhost", port))
        
        cr = build_rdp_cr(nla_enabled=nla)
        sock.sendall(cr)
        
        resp = sock.recv(1024)
        if resp and len(resp) >= 11:
            if resp[5] == 0xd0:
                neg_type = resp[11] if len(resp) > 11 else 0
                if neg_type == 0x02:
                    print(f"OK - Server accepts {mode}")
                    return True
                elif neg_type == 0x03:
                    print(f"FAIL - Server requires different auth")
                else:
                    print(f"OK - Response type 0x{neg_type:02x}")
                    return True
            else:
                print(f"Unexpected PDU: 0x{resp[5]:02x}")
        else:
            print(f"Short response: {len(resp)}b")
        sock.close()
    except Exception as e:
        print(f"ERROR: {e}")
    return False

print("=== RDP Authentication Mode Test ===\n")
test_rdp_auth(3390, True)
test_rdp_auth(3390, False)
