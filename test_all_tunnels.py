import socket

def test_tcp_port(port, name, timeout=3):
    print(f"[*] {name} (localhost:{port})...", end=" ", flush=True)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)
        sock.connect(("localhost", port))
        sock.send(b"\x00\x00\x00\x01")
        try:
            data = sock.recv(1024)
            if data:
                print(f"ACTIVE ({len(data)}b: {data[:16].hex()})")
                return True
            else:
                print("OPEN (no data)")
        except socket.timeout:
            print("OPEN (no response)")
        sock.close()
        return True
    except ConnectionRefusedError:
        print("CLOSED")
        return False
    except socket.timeout:
        print("TIMEOUT")
        return False
    except Exception as e:
        print(f"ERROR: {e}")
        return False

ports = [
    (3390, "RDP"),
    (50051, "VDJ-Proxy"),
    (21115, "RustDesk-ID"),
    (21116, "RustDesk-Relay"),
    (21117, "RustDesk-Server"),
    (21118, "RustDesk-Web"),
    (5985, "WinRM"),
]

print("=== Testing All Tunnel Endpoints ===\n")
active = []
for port, name in ports:
    if test_tcp_port(port, name):
        active.append((port, name))

print(f"\n=== {len(active)}/{len(ports)} endpoints reachable ===")
