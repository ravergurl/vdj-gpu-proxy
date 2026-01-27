import socket
import struct

rdp_connection_request = bytes(
    [
        0x03,
        0x00,
        0x00,
        0x13,
        0x0E,
        0xE0,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
        0x01,
        0x00,
        0x08,
        0x00,
        0x00,
        0x00,
        0x00,
        0x00,
    ]
)


def test_tunnel_rdp(hostname, port_local):
    print(f"\n[*] Testing tunnel: {hostname} -> localhost:{port_local}")

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.settimeout(10)

    try:
        print(f"    [+] Connecting to localhost:{port_local}...")
        sock.connect(("localhost", port_local))
        print(f"    [+] Connected!")

        print(
            f"    [+] Sending RDP Connection Request ({len(rdp_connection_request)} bytes)..."
        )
        sock.sendall(rdp_connection_request)
        print(f"    [+] Sent!")

        print(f"    [+] Waiting for response...")
        response = sock.recv(4096)

        if len(response) > 0:
            print(f"    [+] Received {len(response)} bytes")
            print(f"    [+] Hex dump: {response[:50].hex()}")
            print(f"    [+] ASCII: {repr(response[:50])}")

            if response[:2] == b"\x03\x00":
                tpkt_length = struct.unpack(">H", response[2:4])[0]
                print(f"    [+] Valid RDP TPKT header detected")
                print(f"    [+] TPKT length: {tpkt_length}")

                if len(response) >= 5 and response[4] in [0xD0, 0xE0]:
                    print(f"    [+] X.224 Connection Confirm detected")
                    print(f"    [+] RDP SERVER IS WORKING!")
                    return True
                elif len(response) >= 5 and response[4] == 0xC0:
                    print(f"    [+] X.224 Connection Request Echo")
                else:
                    print(f"    [-] Unexpected X.224 PDU type: 0x{response[4]:02x}")
            else:
                print(
                    f"    [-] Not RDP protocol (expected 03 00, got {response[:2].hex()})"
                )
        else:
            print(f"    [-] No response received")

        return False

    except socket.timeout:
        print(f"    [-] Timeout - no response from server")
        return False
    except ConnectionRefusedError:
        print(f"    [-] Connection refused")
        return False
    except Exception as e:
        print(f"    [-] Error: {e}")
        return False
    finally:
        sock.close()


print("=== RDP Tunnel Debug Tool ===")

print("\n[*] Starting new RDP-mode tunnel on port 17389...")
import subprocess
import time

proc = subprocess.Popen(
    [
        "cloudflared",
        "access",
        "rdp",
        "--hostname",
        "rdp.ai-smith.net",
        "--url",
        "localhost:17389",
    ],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
)

time.sleep(3)

test_tunnel_rdp("rdp.ai-smith.net", 17389)

print("\n[*] Killing tunnel...")
proc.kill()
