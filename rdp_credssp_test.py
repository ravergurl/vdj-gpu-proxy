import socket
import ssl
import struct

def test_credssp(host, port, username, domain=""):
    print(f"[*] Testing CredSSP with {domain}\{username} on {host}:{port}...")
    
    cookie = f"Cookie: mstshash={username}\r\n".encode()
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
        print(f"    Response: {resp[:20].hex()}")
        
        if resp[5] == 0xd0:
            print(f"    [+] Connection accepted, proceeding to TLS...")
            
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            
            ssl_sock = ctx.wrap_socket(sock, server_hostname=host)
            print(f"    [+] TLS established")
            
            cert = ssl_sock.getpeercert()
            if cert:
                print(f"    [+] Server cert: {cert.get('subject', 'N/A')}")
            
            print(f"    [+] CredSSP/NLA auth would happen next (needs NTLM/Kerberos)")
            print(f"    [!] To complete auth, use: mstsc /v:localhost:{port}")
            print(f"    [!] Try username formats:")
            print(f"        - mikeb")
            print(f"        - .\mikeb")
            print(f"        - meltat0\mikeb")
            print(f"        - cryptsmith@gmail.com (if MS account)")
            
            ssl_sock.close()
            return True
        else:
            print(f"    [-] Connection rejected")
            
        sock.close()
    except Exception as e:
        print(f"    [-] Error: {e}")
    return False

test_credssp("localhost", 3390, "mikeb")
