import socket
import struct
import ssl

def check_bluekeep(host, port):
    print(f"[*] Checking BlueKeep (CVE-2019-0708) on {host}:{port}...")
    
    cookie = b"Cookie: mstshash=test\r\n"
    neg_req = bytes([0x01, 0x00, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00])
    x224_data = bytes([0xe0, 0x00, 0x00, 0x00, 0x00, 0x00]) + cookie + neg_req
    x224_header = bytes([len(x224_data)])
    cr = bytes([0x03, 0x00]) + struct.pack(">H", 4 + 1 + len(x224_data)) + x224_header + x224_data
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((host, port))
        sock.sendall(cr)
        resp = sock.recv(1024)
        
        if len(resp) >= 19:
            selected_proto = resp[15] if len(resp) > 15 else 0
            if selected_proto == 0:
                print(f"    [!] Server accepts PROTOCOL_RDP (no NLA) - potential BlueKeep target")
                return True
            else:
                print(f"    [-] Server requires NLA (protocol {selected_proto}) - BlueKeep mitigated")
        sock.close()
    except Exception as e:
        print(f"    [-] Error: {e}")
    return False

def check_rdp_version(host, port):
    print(f"[*] Getting RDP/Windows version info...")
    
    cookie = b"Cookie: mstshash=version\r\n"
    neg_req = bytes([0x01, 0x00, 0x08, 0x00, 0x03, 0x00, 0x00, 0x00])
    x224_data = bytes([0xe0, 0x00, 0x00, 0x00, 0x00, 0x00]) + cookie + neg_req
    x224_header = bytes([len(x224_data)])
    cr = bytes([0x03, 0x00]) + struct.pack(">H", 4 + 1 + len(x224_data)) + x224_header + x224_data
    
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((host, port))
        sock.sendall(cr)
        resp = sock.recv(1024)
        
        if resp[5] == 0xd0:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            ssl_sock = ctx.wrap_socket(sock, server_hostname=host)
            
            cert_bin = ssl_sock.getpeercert(binary_form=True)
            with open("C:/Users/peopl/work/vdj/rdp_cert.der", "wb") as f:
                f.write(cert_bin)
            
            ssl_sock.close()
            return True
    except Exception as e:
        print(f"    [-] Error: {e}")
    return False

def try_null_session(host, port):
    print(f"[*] Testing null/blank password auth...")
    print(f"    (Automated NTLM auth not implemented - would need impacket)")

print("=== RDP Vulnerability Scanner ===\n")
check_bluekeep("localhost", 3390)
check_rdp_version("localhost", 3390)
try_null_session("localhost", 3390)
