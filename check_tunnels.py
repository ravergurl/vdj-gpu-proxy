import socket
import time


def check_port(port):
    print(f"[*] Checking localhost:{port}...", end=" ", flush=True)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(("localhost", port))
        if result == 0:
            print("OPEN", end=" ")
            try:
                sock.send(b"\x00\x00\x00\x00")
                data = sock.recv(1024)
                if data:
                    print(f" (Received {len(data)} bytes: {data[:20].hex()})")
                else:
                    print(" (No data)")
            except:
                print(" (Connected, no response)")
        else:
            print("CLOSED")
        sock.close()
    except Exception as e:
        print(f"ERROR: {e}")


ports = [3390, 21115, 21116, 21117, 5985]
for port in ports:
    check_port(port)
