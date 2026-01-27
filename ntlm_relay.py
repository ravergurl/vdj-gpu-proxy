import socket
import struct

def create_ntlm_negotiate():
    signature = b"NTLMSSP\x00"
    msg_type = struct.pack("<I", 1)
    flags = struct.pack("<I", 0xe2088297)
    domain_len = struct.pack("<HH", 0, 0)
    domain_offset = struct.pack("<I", 0)
    workstation_len = struct.pack("<HH", 0, 0)
    workstation_offset = struct.pack("<I", 0)
    return signature + msg_type + flags + domain_len + domain_offset + workstation_len + workstation_offset

def smb_negotiate(host, port):
    print(f"[*] SMB Negotiate to {host}:{port}...")
    
    smb_header = (
        b"\xfeSMB"
        b"\x40\x00"
        b"\x00\x00"
        b"\x00\x00"
        b"\x00\x00"
        b"\x00\x00\x00\x00"
        b"\x00\x00\x00\x00"
        b"\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\xff\xfe\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00"
    )
    
    neg_req = (
        b"\x24\x00"
        b"\x02\x00"
        b"\x01\x00"
        b"\x00\x00"
        b"\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x78\x00"
        b"\x00\x00"
        b"\x02\x02"
        b"\x10\x02"
    )
    
    packet = smb_header + neg_req
    netbios = struct.pack(">I", len(packet))[1:4]
    netbios = b"\x00" + netbios
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((host, port))
        sock.sendall(netbios + packet)
        
        resp = sock.recv(4096)
        if resp and len(resp) > 4:
            print(f"    [+] Got response: {len(resp)} bytes")
            if b"\xfeSMB" in resp or b"\xffSMB" in resp:
                print(f"    [+] SMB Protocol detected!")
                print(f"    [+] Response header: {resp[:64].hex()}")
                return True
            else:
                print(f"    [-] Not SMB: {resp[:20].hex()}")
        sock.close()
    except socket.timeout:
        print(f"    [-] Timeout")
    except ConnectionRefusedError:
        print(f"    [-] Connection refused")
    except Exception as e:
        print(f"    [-] Error: {e}")
    return False

def try_null_smb_session(host, port):
    print(f"\n[*] Attempting null SMB session...")
    smb_negotiate(host, port)

print("=== NTLM/SMB Attack Vector ===\n")

powershell -Command "Start-Process -NoNewWindow -FilePath 'cloudflared.exe' -ArgumentList 'access','tcp','--hostname','smb.ai-smith.net','--url','localhost:44445'"

import time
time.sleep(2)

try_null_smb_session("localhost", 44445)
