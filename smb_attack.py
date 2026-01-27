import socket
import struct
import time

def smb2_negotiate(host, port):
    print(f"[*] SMB2 Negotiate to {host}:{port}...")
    
    smb2_header = bytearray(64)
    smb2_header[0:4] = b"\xfeSMB"
    smb2_header[4:6] = struct.pack("<H", 64)
    smb2_header[12:14] = struct.pack("<H", 0)
    smb2_header[16:24] = struct.pack("<Q", 0)
    smb2_header[24:28] = struct.pack("<I", 0)
    smb2_header[28:32] = struct.pack("<I", 0)
    smb2_header[32:40] = struct.pack("<Q", 0)
    smb2_header[40:44] = struct.pack("<I", 0xFFFE)
    
    neg_context = struct.pack("<H", 36)
    neg_context += struct.pack("<H", 2)
    neg_context += struct.pack("<H", 1)
    neg_context += struct.pack("<H", 0)
    neg_context += struct.pack("<I", 0)
    neg_context += b"\x00" * 16
    neg_context += struct.pack("<I", 0x68)
    neg_context += struct.pack("<H", 0)
    neg_context += struct.pack("<H", 0x0202)
    neg_context += struct.pack("<H", 0x0210)
    
    packet = bytes(smb2_header) + neg_context
    netbios = b"\x00" + struct.pack(">I", len(packet))[1:4]
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((host, port))
        sock.sendall(netbios + packet)
        
        resp = sock.recv(4096)
        if resp:
            print(f"    [+] Response: {len(resp)} bytes")
            if b"\xfeSMB" in resp:
                print(f"    [+] SMB2 detected!")
                if len(resp) > 72:
                    dialect = struct.unpack("<H", resp[72:74])[0] if len(resp) > 74 else 0
                    print(f"    [+] Dialect: 0x{dialect:04x}")
                return resp
        sock.close()
    except Exception as e:
        print(f"    [-] {e}")
    return None

time.sleep(2)
print("=== SMB Attack via Tunnel ===\n")
smb2_negotiate("localhost", 44445)
