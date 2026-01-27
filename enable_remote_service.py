import urllib.request
import json
import socket
import subprocess
import time

CF_TOKEN = "ySIb_2uMzHQDvnK5MulcCvOiRKsC6k0pH188bG8Y"
ACCOUNT_ID = "4c2932bc3381be38d5266241b16be092"
TUNNEL_ID = "926eac5e-2642-4a16-9edc-c06b6c705ab8"

print("=== REMOTE SERVICE ENABLEMENT ATTEMPTS ===\n")

print("[1] Checking if Windows Remote Management can be enabled via tunnel config...")
print("    Cloudflared only forwards existing services, cannot start new ones")

print("\n[2] Checking for PowerShell Remoting ports...")
ps_ports = [5985, 5986, 47001]
for port in ps_ports:
    subprocess.run(["powershell", "-Command", 
        f"Start-Process -NoNewWindow -FilePath 'cloudflared.exe' -ArgumentList 'access','tcp','--hostname','winrm.ai-smith.net','--url','localhost:{port}'"],
        capture_output=True)

time.sleep(2)

for port in ps_ports:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        if sock.connect_ex(("localhost", port)) == 0:
            sock.send(b"GET /wsman HTTP/1.1\r\nHost: localhost\r\n\r\n")
            try:
                resp = sock.recv(1024)
                if resp:
                    print(f"    [+] Port {port}: {resp[:100]}")
            except:
                print(f"    [+] Port {port}: Connected but no HTTP response")
        sock.close()
    except Exception as e:
        pass

print("\n[3] Attempting to trigger Windows services via DCOM...")
print("    Port 135 (RPC Endpoint Mapper) needed but likely blocked")

print("\n[4] Checking WMI over DCOM (port 135)...")
headers = {"Authorization": f"Bearer {CF_TOKEN}", "Content-Type": "application/json"}

wmi_config = {
    "config": {
        "ingress": [
            {"hostname": "rdp.ai-smith.net", "service": "tcp://localhost:3389"},
            {"hostname": "wmi.ai-smith.net", "service": "tcp://localhost:135"},
            {"hostname": "dcom.ai-smith.net", "service": "tcp://localhost:135"},
            {"hostname": "smb.ai-smith.net", "service": "tcp://localhost:445"},
            {"hostname": "netbios.ai-smith.net", "service": "tcp://localhost:139"},
            {"hostname": "ldap.ai-smith.net", "service": "tcp://localhost:389"},
            {"service": "http_status:404"}
        ],
        "warp-routing": {"enabled": True}
    }
}

try:
    req = urllib.request.Request(
        f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/cfd_tunnel/{TUNNEL_ID}/configurations",
        data=json.dumps(wmi_config).encode(),
        headers=headers,
        method="PUT"
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        data = json.loads(resp.read())
        print(f"    [+] Config updated to v{data['result']['version']}")
except Exception as e:
    print(f"    [-] Config update failed: {e}")

print("\n[5] Starting local tunnel listeners for Windows services...")
services = [
    ("wmi.ai-smith.net", 10135),
    ("smb.ai-smith.net", 10445),
    ("netbios.ai-smith.net", 10139),
    ("ldap.ai-smith.net", 10389),
]

for hostname, local_port in services:
    subprocess.Popen(
        ["cloudflared", "access", "tcp", "--hostname", hostname, "--url", f"localhost:{local_port}"],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )

time.sleep(3)

print("\n[6] Testing Windows service availability through tunnels...")
for hostname, local_port in services:
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(("localhost", local_port))
        if result == 0:
            sock.send(b"\x00\x00\x00\x01")
            try:
                data = sock.recv(1024)
                if data:
                    print(f"    [+] {hostname}:{local_port} - ACTIVE ({len(data)}b)")
                else:
                    print(f"    [+] {hostname}:{local_port} - OPEN (tunnel connected)")
            except:
                print(f"    [+] {hostname}:{local_port} - OPEN (no service response)")
        else:
            print(f"    [-] {hostname}:{local_port} - CLOSED")
        sock.close()
    except Exception as e:
        print(f"    [-] {hostname}:{local_port} - ERROR: {e}")
