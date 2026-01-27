import socket
import time

print("=== Testing Tunnel RDP Access ===")

ports_to_test = [15389, 3389, 3390, 14389, 33389]

for port in ports_to_test:
    print(f"\n[*] Testing localhost:{port}")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        sock.connect(("localhost", port))

        data = sock.recv(1024)
        if data and len(data) > 0:
            print(f"    [+] Port {port} RESPONDING")
            print(f"    [+] Response: {len(data)} bytes")
            if b"\x03\x00" in data[:10]:
                print(f"    [+] RDP PROTOCOL DETECTED!")
                print(f"    [+] Connect with: mstsc /v:localhost:{port}")
        else:
            print(f"    [-] Port {port} connected but no data")
        sock.close()
    except socket.timeout:
        print(f"    [-] Port {port} timeout")
    except ConnectionRefusedError:
        print(f"    [-] Port {port} refused")
    except OSError as e:
        print(f"    [-] Port {port} error: {e}")

    time.sleep(0.5)
