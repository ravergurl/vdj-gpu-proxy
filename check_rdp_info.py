import socket
import ssl
import struct

def rdp_get_server_info(host, port):
    print(f"[*] Extracting RDP server info from {host}:{port}...")
    
    cookie = b"Cookie: mstshash=probe\r\n"
    neg_req = bytes([0x01, 0x00, 0x08, 0x00, 0x0b, 0x00, 0x00, 0x00])
    x224_data = bytes([0xe0, 0x00, 0x00, 0x00, 0x00, 0x00]) + cookie + neg_req
    x224_header = bytes([len(x224_data)])
    cr = bytes([0x03, 0x00]) + struct.pack(">H", 4 + 1 + len(x224_data)) + x224_header + x224_data
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)
    sock.connect((host, port))
    sock.sendall(cr)
    
    resp = sock.recv(1024)
    print(f"    Response: {resp.hex()}")
    
    if resp[5] == 0xd0 and len(resp) > 11:
        neg_resp_type = resp[11]
        neg_flags = resp[12]
        print(f"    Negotiation Type: 0x{neg_resp_type:02x}")
        print(f"    Flags: 0x{neg_flags:02x}")
        
        if neg_resp_type == 0x02:
            protocol = struct.unpack("<I", resp[12:16])[0] if len(resp) >= 16 else 0
            protocols = []
            if protocol & 0x01: protocols.append("TLS")
            if protocol & 0x02: protocols.append("CredSSP/NLA")
            if protocol & 0x08: protocols.append("RDSTLS")
            print(f"    Selected Protocol: {', '.join(protocols) if protocols else 'RDP'}")
    
    ctx = ssl.create_default_context()
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    
    try:
        ssl_sock = ctx.wrap_socket(sock, server_hostname=host)
        cert = ssl_sock.getpeercert(binary_form=True)
        if cert:
            print(f"    [+] Got TLS cert ({len(cert)} bytes)")
            import ssl as ssl_mod
            cert_dict = ssl_sock.getpeercert()
            if cert_dict:
                print(f"    Certificate: {cert_dict}")
    except Exception as e:
        print(f"    TLS error: {e}")
    
    sock.close()

rdp_get_server_info("localhost", 3390)
