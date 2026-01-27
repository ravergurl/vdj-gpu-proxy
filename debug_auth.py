import socket
import struct
import ssl
import hmac
import os
import time
import traceback

def md4(data):
    def left_rotate(x, n): return ((x << n) | (x >> (32 - n))) & 0xffffffff
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

def debug_auth(host, port, user, pwd, dom):
    print(f"\n{'='*50}")
    print(f"DEBUG AUTH: {dom}\{user}:{pwd}")
    print(f"{'='*50}")
    
    try:
        print("[1] X.224 Connection Request...")
        cookie = f"Cookie: mstshash={user}\r\n".encode()
        neg = bytes([0x01,0x00,0x08,0x00,0x03,0x00,0x00,0x00])
        x224 = bytes([0xe0,0,0,0,0,0]) + cookie + neg
        cr = bytes([0x03,0x00]) + struct.pack(">H", 5+len(x224)) + bytes([len(x224)]) + x224
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(15)
        sock.connect((host, port))
        sock.sendall(cr)
        resp = sock.recv(1024)
        print(f"    Response: {resp[:20].hex()}")
        if resp[5] != 0xd0:
            print("    REJECTED at X.224 level")
            return
        print("    OK - Connection confirmed")
        
        print("[2] TLS Handshake...")
        ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ctx.check_hostname = False
        ctx.verify_mode = ssl.CERT_NONE
        ss = ctx.wrap_socket(sock, server_hostname=host)
        print(f"    OK - TLS version: {ss.version()}")
        
        print("[3] CredSSP Negotiate (NTLM Type 1)...")
        ntlm_neg = b"NTLMSSP\x00\x01\x00\x00\x00\xb7\x82\x08\xe2" + b"\x00"*16 + b"\x0a\x00\x63\x45\x00\x00\x00\x0f"
        credssp_neg = bytes([0x30,0x37,0xa0,0x03,0x02,0x01,0x06,0xa1,0x30,0x30,0x2e,0x30,0x2c,0xa0,0x2a,0x04,0x28]) + ntlm_neg
        print(f"    Sending {len(credssp_neg)} bytes")
        ss.send(credssp_neg)
        
        print("[4] Receiving Challenge (NTLM Type 2)...")
        chalresp = ss.recv(4096)
        print(f"    Received {len(chalresp)} bytes")
        print(f"    First 30 bytes: {chalresp[:30].hex()}")
        
        if b"NTLMSSP" not in chalresp:
            print("    ERROR: No NTLMSSP in response!")
            return
        
        nm = chalresp[chalresp.find(b"NTLMSSP"):]
        schal = nm[24:32]
        print(f"    Server challenge: {schal.hex()}")
        
        ti_len = struct.unpack("<H", nm[40:42])[0]
        ti_off = struct.unpack("<I", nm[44:48])[0]
        ti = nm[ti_off:ti_off+ti_len]
        print(f"    Target info: {ti_len} bytes at offset {ti_off}")
        
        ts = None
        i = 0
        while i < len(ti)-4:
            aid, alen = struct.unpack("<HH", ti[i:i+4])
            if aid == 7: ts = ti[i+4:i+12]; break
            if aid == 0: break
            i += 4 + alen
        if not ts:
            ts = struct.pack("<Q", int(time.time()*10000000)+116444736000000000)
        print(f"    Timestamp: {ts.hex()}")
        
        print("[5] Building NTLM Type 3 (Authenticate)...")
        nth = ntlm_hash(pwd)
        print(f"    NTLM hash: {nth.hex()}")
        cchal = os.urandom(8)
        ntr = ntlmv2_resp(nth, user, dom, schal, cchal, ts, ti)
        lmr = cchal + b'\x00'*16
        
        db = dom.encode('utf-16le')
        ub = user.encode('utf-16le')
        wb = b'W\x00O\x00R\x00K\x00'
        
        print(f"    Domain: {dom} ({len(db)} bytes)")
        print(f"    User: {user} ({len(ub)} bytes)")
        
        off = 88
        am = b'NTLMSSP\x00\x03\x00\x00\x00'
        am += struct.pack('<HHI', len(lmr), len(lmr), off); off += len(lmr)
        am += struct.pack('<HHI', len(ntr), len(ntr), off); off += len(ntr)
        am += struct.pack('<HHI', len(db), len(db), off); off += len(db)
        am += struct.pack('<HHI', len(ub), len(ub), off); off += len(ub)
        am += struct.pack('<HHI', len(wb), len(wb), off); off += len(wb)
        am += struct.pack('<HHI', 0, 0, off)
        am += struct.pack('<I', 0xe2888215)
        am += b'\x0a\x00\x63\x45\x00\x00\x00\x0f'
        am += lmr + ntr + db + ub + wb
        
        print(f"    Auth message: {len(am)} bytes")
        
        print("[6] Wrapping in CredSSP...")
        al = len(am)
        ca = bytes([0x30,0x82]) + struct.pack(">H", al+15)
        ca += bytes([0xa0,0x03,0x02,0x01,0x06])
        ca += bytes([0xa2,0x82]) + struct.pack(">H", al+6)
        ca += bytes([0x30,0x82]) + struct.pack(">H", al+2)
        ca += bytes([0x04,0x82]) + struct.pack(">H", al)
        ca += am
        print(f"    CredSSP packet: {len(ca)} bytes")
        print(f"    Header: {ca[:20].hex()}")
        
        print("[7] Sending authentication...")
        ss.send(ca)
        
        print("[8] Waiting for response...")
        try:
            ss.settimeout(5)
            ar = ss.recv(4096)
            print(f"    Received {len(ar)} bytes")
            print(f"    Response: {ar[:50].hex() if ar else 'empty'}")
            
            if ar and len(ar) > 0:
                if ar[0] == 0x30:
                    print("    [+] Got ASN.1 SEQUENCE - server responded!")
                    if b'\xa3' in ar[:30]:
                        print("    [+] Contains pubKeyAuth - AUTH SUCCESS!")
                        return True
                    else:
                        print("    [?] No pubKeyAuth - may need more protocol steps")
                else:
                    print(f"    [-] Unexpected response type: 0x{ar[0]:02x}")
            else:
                print("    [-] Empty response")
                
        except ssl.SSLError as e:
            err = str(e)
            print(f"    SSL Error: {err}")
            if "internal error" in err.lower():
                print("    -> This is AUTH REJECTION (server closed TLS)")
            elif "unexpected eof" in err.lower():
                print("    -> Server disconnected (likely auth failure)")
            else:
                print("    -> Protocol error, not necessarily auth failure")
                
        except socket.timeout:
            print("    Timeout - server may be processing or hung")
            
        ss.close()
        
    except Exception as e:
        print(f"ERROR: {e}")
        traceback.print_exc()

print("=== DETAILED CREDENTIAL DEBUG ===\n")

debug_auth("localhost", 3390, "administrator", "1121", "meltat0")
debug_auth("localhost", 3390, "administrator", "1121", "MELTAT0")
debug_auth("localhost", 3390, "kuro", "1121", "meltat0")
debug_auth("localhost", 3390, "melody", "0114", "meltat0")
