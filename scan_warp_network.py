import socket
import threading
from queue import Queue
import time

SUBNETS = [("192.168.1.", 24), ("10.100.0.", 24)]
PORTS = [445, 3389, 22, 5985, 80]

print_lock = threading.Lock()


def scan_target(ip, port):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        result = s.connect_ex((ip, port))
        if result == 0:
            with print_lock:
                print(f"[+] Found open {ip}:{port}")
        s.close()
    except:
        pass


def worker(q):
    while True:
        task = q.get()
        if task is None:
            break
        ip, port = task
        scan_target(ip, port)
        q.task_done()


def main():
    q = Queue()
    threads = []

    # Start threads
    for _ in range(50):
        t = threading.Thread(target=worker, args=(q,))
        t.start()
        threads.append(t)

    print("Scanning subnets...")
    for prefix, size in SUBNETS:
        for i in range(1, 255):
            ip = f"{prefix}{i}"
            for port in PORTS:
                q.put((ip, port))

    q.join()

    # Stop threads
    for _ in range(50):
        q.put(None)
    for t in threads:
        t.join()

    print("Scan complete")


if __name__ == "__main__":
    main()
