import socket
import time

# Try common IPs in 192.168.1.0/24 subnet
TARGETS = [
    "192.168.1.1",
    "192.168.1.10",
    "192.168.1.100",
    "192.168.1.104",
    "192.168.1.254",
]
PORT = 445

print("Testing SMB connection via WARP network...")
print(f"Targets: {TARGETS}")
print(f"Port: {PORT}")

for target in TARGETS:
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        result = s.connect_ex((target, PORT))
        if result == 0:
            print(f"[+] SMB PORT OPEN on {target}:{PORT}")
            print(f"    Try: smbclient //\\\\{target}\\C$ -U melody -W")
            print(f"    Try: smbclient //{target}/ipc$ -U meltat0")
        s.close()
    except Exception as e:
        print(f"[-] {target}:{PORT} - {e}")

print("\nScan complete")
