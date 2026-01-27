import socket

ports = [
    (3390, "RDP"),
    (4445, "SMB"),
    (5985, "WinRM-HTTP"),
    (5986, "WinRM-HTTPS"),
    (10135, "WMI/RPC"),
]

print("=== Testing Admin Ports via Tunnel ===\n")
for port, name in ports:
    print(f"[*] {name} (:{port})...", end=" ", flush=True)
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        result = sock.connect_ex(("localhost", port))
        if result == 0:
            sock.send(b"\x00")
            try:
                data = sock.recv(512)
                if data:
                    print(f"ACTIVE - got {len(data)}b")
                else:
                    print("OPEN")
            except:
                print("OPEN (no response)")
        else:
            print("CLOSED")
        sock.close()
    except Exception as e:
        print(f"ERROR: {e}")
