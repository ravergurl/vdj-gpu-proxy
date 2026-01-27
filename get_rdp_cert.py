import socket
import ssl
import struct

def get_rdp_cert(host, port):
    cookie = b"Cookie: mstshash=probe\r\n"
    neg_req = bytes([0x01, 0x00, 0x08, 0x00, 0x03, 0x00, 0x00, 0x00])
    x224_data = bytes([0xe0, 0x00, 0x00, 0x00, 0x00, 0x00]) + cookie + neg_req
    x224_header = bytes([len(x224_data)])
    cr = bytes([0x03, 0x00]) + struct.pack(">H", 4 + 1 + len(x224_data)) + x224_header + x224_data
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    sock.connect((host, port))
    sock.sendall(cr)
    sock.recv(1024)
    
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    ssl_sock = ctx.wrap_socket(sock, server_hostname=host)
    cert_bin = ssl_sock.getpeercert(binary_form=True)
    
    with open("rdp_cert.der", "wb") as f:
        f.write(cert_bin)
    print(f"[+] Saved certificate to rdp_cert.der ({len(cert_bin)} bytes)")
    
    ssl_sock.close()

get_rdp_cert("localhost", 3390)
