import socket
import time


def test_rdp_port(port, timeout=5):
    print(f"\n[*] Testing RDP handshake on localhost:{port}")
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(timeout)

        print(f"    [+] Connecting...")
        sock.connect(("localhost", port))
        print(f"    [+] Connected!")

        print(f"    [+] Waiting for RDP server hello...")
        data = sock.recv(4096)

        if data and len(data) > 0:
            print(f"    [+] Received {len(data)} bytes")
            print(f"    [+] First 20 bytes (hex): {data[:20].hex()}")

            if data[:2] == b"\x03\x00":
                print(f"    [+] ✓ VALID RDP PROTOCOL DETECTED!")
                print(f"    [+] Server is responding correctly")
                return True
            else:
                print(f"    [-] Unexpected protocol response")
                return False
        else:
            print(f"    [-] No data received (timeout)")
            return False

        sock.close()

    except socket.timeout:
        print(f"    [-] Connection timeout after {timeout}s")
        print(f"    [-] Server not responding to RDP handshake")
        return False
    except ConnectionRefusedError:
        print(f"    [-] Connection refused")
        print(f"    [-] Port not listening")
        return False
    except Exception as e:
        print(f"    [-] Error: {type(e).__name__}: {e}")
        return False


print("=== RDP Handshake Test ===")
print("Testing cloudflared RDP tunnels...")

results = {}
ports = [16389, 15389]

for port in ports:
    results[port] = test_rdp_port(port)
    time.sleep(1)

print("\n=== Summary ===")
for port, success in results.items():
    status = "✓ WORKING" if success else "✗ FAILED"
    print(f"Port {port}: {status}")

working_ports = [p for p, s in results.items() if s]
if working_ports:
    print(f"\n[+] Connect with: mstsc /v:localhost:{working_ports[0]}")
else:
    print("\n[-] No working RDP tunnels found")
