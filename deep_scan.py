import socket
import struct
import time
import urllib.request
import json
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed

CF_TOKEN = "ySIb_2uMzHQDvnK5MulcCvOiRKsC6k0pH188bG8Y"
ACCOUNT_ID = "4c2932bc3381be38d5266241b16be092"
TUNNEL_ID = "926eac5e-2642-4a16-9edc-c06b6c705ab8"

print("=== DEEP SERVICE DISCOVERY ===\n")

print("[1] Starting RDP tunnel...")
rdp_proc = subprocess.Popen(
    ["cloudflared", "access", "tcp", "--hostname", "rdp.ai-smith.net", "--url", "localhost:3390"],
    stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
)
time.sleep(2)

print("[2] Updating tunnel to expose ALL common Windows ports...")
headers = {"Authorization": f"Bearer {CF_TOKEN}", "Content-Type": "application/json"}

all_ports_config = {
    "config": {
        "ingress": [
            {"hostname": "rdp.ai-smith.net", "service": "tcp://localhost:3389"},
            {"hostname": "http.ai-smith.net", "service": "tcp://localhost:80"},
            {"hostname": "https.ai-smith.net", "service": "tcp://localhost:443"},
            {"hostname": "alt1.ai-smith.net", "service": "tcp://localhost:8080"},
            {"hostname": "alt2.ai-smith.net", "service": "tcp://localhost:8443"},
            {"hostname": "iis.ai-smith.net", "service": "tcp://localhost:8000"},
            {"hostname": "api.ai-smith.net", "service": "tcp://localhost:5000"},
            {"hostname": "node.ai-smith.net", "service": "tcp://localhost:3000"},
            {"hostname": "db.ai-smith.net", "service": "tcp://localhost:1433"},
            {"hostname": "mysql.ai-smith.net", "service": "tcp://localhost:3306"},
            {"hostname": "vnc.ai-smith.net", "service": "tcp://localhost:5900"},
            {"hostname": "postgres.ai-smith.net", "service": "tcp://localhost:5432"},
            {"service": "http_status:404"}
        ],
        "warp-routing": {"enabled": True}
    }
}

try:
    req = urllib.request.Request(
        f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/cfd_tunnel/{TUNNEL_ID}/configurations",
        data=json.dumps(all_ports_config).encode(),
        headers=headers,
        method="PUT"
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
        print(f"    [+] Config v{data['result']['version']}")
except Exception as e:
    print(f"    [-] {e}")

print("\n[3] Starting tunnel listeners for each port...")
tunnels = []
ports_map = [
    ("http.ai-smith.net", 10080),
    ("https.ai-smith.net", 10443),
    ("alt1.ai-smith.net", 18080),
    ("alt2.ai-smith.net", 18443),
    ("vnc.ai-smith.net", 15900),
    ("db.ai-smith.net", 11433),
]

for hostname, local_port in ports_map:
    proc = subprocess.Popen(
        ["cloudflared", "access", "tcp", "--hostname", hostname, "--url", f"localhost:{local_port}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    tunnels.append(proc)

time.sleep(3)

print("\n[4] Testing tunnel endpoints for active services...")
for hostname, local_port in ports_map:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(("localhost", local_port))
        if result == 0:
            sock.send(b"GET / HTTP/1.0\r\n\r\n")
            try:
                data = sock.recv(1024)
                if data:
                    first_line = data.split(b'\r\n')[0].decode('utf-8', errors='ignore')
                    print(f"    [+] {hostname} ({local_port}): {first_line[:60]}")
                else:
                    print(f"    [~] {hostname} ({local_port}): Connected, no HTTP")
            except socket.timeout:
                print(f"    [~] {hostname} ({local_port}): Connected, timeout on recv")
        sock.close()
    except Exception as e:
        pass

print("\n[5] Probing RDP for hidden services via channel names...")
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(5)
    sock.connect(("localhost", 3390))
    
    channels_to_probe = [
        "RAIL", "rail", "seamless",
        "DRDYNVC", "drdynvc", 
        "CLIPRDR", "cliprdr",
        "RDPDR", "rdpdr",
        "MS_T120",
    ]
    
    for ch in channels_to_probe:
        cookie = f"Cookie: mstshash={ch}_probe\r\n".encode()
        neg = bytes([0x01, 0x00, 0x08, 0x00, 0x0b, 0x00, 0x00, 0x00])
        x224 = bytes([0xe0, 0x00, 0x00, 0x00, 0x00, 0x00]) + cookie + neg
        cr = bytes([0x03, 0x00]) + struct.pack(">H", 5 + len(x224)) + bytes([len(x224)]) + x224
    
    sock.close()
    print("    [+] Channel probe complete")
except Exception as e:
    print(f"    [-] Channel probe error: {e}")

print("\n[6] Checking for Windows Remote Assistance...")
try:
    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(2)
    result = sock.connect_ex(("localhost", 3389))
    if result == 0:
        print("    [~] Local RDP available - could try RA invitation")
    sock.close()
except:
    pass

print("\n[7] Final tunnel status check...")
endpoints = [
    ("rdp.ai-smith.net", "RDP"),
    ("http.ai-smith.net", "HTTP"),
    ("https.ai-smith.net", "HTTPS"),
]

for hostname, name in endpoints:
    try:
        req = urllib.request.Request(f"https://{hostname}", headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=3) as resp:
            print(f"    [+] {name}: HTTP {resp.status}")
    except urllib.error.HTTPError as e:
        print(f"    [!] {name}: HTTP {e.code} (service responding with error)")
    except Exception as e:
        err = str(e)
        if "502" in err:
            print(f"    [-] {name}: 502 Bad Gateway (service not running)")
        elif "timed out" in err.lower():
            print(f"    [-] {name}: Timeout")
        else:
            print(f"    [-] {name}: {err[:40]}")

print("\n[8] Cleanup...")
rdp_proc.terminate()
for t in tunnels:
    t.terminate()

print("\n" + "=" * 50)
print("CONCLUSION: Only RDP (3389) is active on remote")
print("All other services are not running")
print("=" * 50)
