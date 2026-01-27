import socket
import sys


def test_rdp(host, port):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(5)
        sock.connect((host, port))

        data = sock.recv(1024)
        if data:
            print(f"[+] RDP SERVICE RESPONDING on {host}:{port}")
            print(f"[+] Response length: {len(data)} bytes")
            print(f"[+] First bytes: {data[:20].hex()}")

            if b"\x03\x00" in data[:4]:
                print("[+] CONFIRMED: Remote Desktop Protocol response detected")
                print("[+] This is the REMOTE server (not localhost loop)")
            return True
        else:
            print(f"[-] Connection established but no response")
            return False
    except socket.timeout:
        print(f"[-] Connection timeout on {host}:{port}")
        return False
    except ConnectionRefusedError:
        print(f"[-] Connection refused on {host}:{port}")
        return False
    except Exception as e:
        print(f"[-] Error: {e}")
        return False
    finally:
        sock.close()


if __name__ == "__main__":
    print("=== Testing RDP Tunnel ===")
    test_rdp("localhost", 14389)
    print("\n=== Testing Direct IP ===")
    test_rdp("192.168.1.104", 3389)
