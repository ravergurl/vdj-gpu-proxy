import socket
import ssl
import struct

def test_rdp_user(host, port, username):
    print(f"[*] Testing RDP with user '{username}' on {host}:{port}...")
    
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
        if resp[5] == 0xd0:
            print(f"    [+] Server accepts connection for '{username}'")
            
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            ssl_sock = ctx.wrap_socket(sock, server_hostname=host)
            
            cert_bin = ssl_sock.getpeercert(binary_form=True)
            print(f"    [+] TLS OK, cert {len(cert_bin)} bytes")
            print(f"")
            print(f"    === CONNECT WITH ===")
            print(f"    mstsc /v:localhost:{port}")
            print(f"")
            print(f"    Username options:")
            print(f"      - {username}")
            print(f"      - meltat0\{username}")
            print(f"      - .\{username}")
            print(f"")
            print(f"    Password: Your Microsoft account password (NOT the PIN)")
            
            ssl_sock.close()
            return True
        sock.close()
    except Exception as e:
        print(f"    [-] Error: {e}")
    return False

test_rdp_user("localhost", 3390, "melody")
