import socket
import concurrent.futures
import time

host = "localhost"
common_ports = [
    80, 443, 8080, 8443, 8000, 8888, 9000, 9090,
    3000, 4000, 5000, 5001, 6000, 7000, 7001,
    1433, 1521, 3306, 5432, 27017, 6379,
    8081, 8082, 8083, 8084, 8085,
    9001, 9002, 9003, 9200, 9300,
    2375, 2376, 10000, 10001,
    50051, 50052,
]

print(f"[*] Scanning {len(common_ports)} common ports via WARP routing...")
print(f"[*] Target: 192.168.1.104")

def check_port_via_warp(port):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(2)
        result = sock.connect_ex(("192.168.1.104", port))
        sock.close()
        return port if result == 0 else None
    except:
        return None

start = time.time()
open_ports = []

with concurrent.futures.ThreadPoolExecutor(max_workers=20) as executor:
    futures = {executor.submit(check_port_via_warp, p): p for p in common_ports}
    for future in concurrent.futures.as_completed(futures):
        result = future.result()
        if result:
            print(f"    [+] Port {result} OPEN")
            open_ports.append(result)

print(f"\n[*] Scan completed in {time.time()-start:.1f}s")
print(f"[*] Open ports: {open_ports if open_ports else 'None found'}")
