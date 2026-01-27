import socket
import threading
from queue import Queue


def scan_port(ip, port, results):
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(1)
        if sock.connect_ex((ip, port)) == 0:
            results.append((ip, port))
        sock.close()
    except:
        pass


def worker(q, port, results):
    while not q.empty():
        ip = q.get()
        scan_port(ip, port, results)
        q.task_done()


def run_scan(subnet, port):
    print(f"[*] Scanning {subnet}.0/24 on port {port}...")
    results = []
    q = Queue()
    for i in range(1, 255):
        q.put(f"{subnet}.{i}")

    threads = []
    for _ in range(20):
        t = threading.Thread(target=worker, args=(q, port, results))
        t.start()
        threads.append(t)

    for t in threads:
        t.join()

    return results


subnet = "192.168.1"
ports = [3389, 21116, 22]

all_found = []
for port in ports:
    found = run_scan(subnet, port)
    for f in found:
        print(f"    [+] Found {f[0]}:{f[1]}")
        all_found.append(f)

print(f"\n[*] Total devices found: {len(all_found)}")
