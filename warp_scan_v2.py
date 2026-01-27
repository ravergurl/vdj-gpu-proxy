import socket
import threading
import subprocess
import time
from queue import Queue


def connect_warp():
    print("Connecting WARP...")
    subprocess.run(["warp-cli", "connect"], capture_output=True)
    time.sleep(5)

    # Check status
    res = subprocess.run(["warp-cli", "status"], capture_output=True, text=True)
    print(res.stdout)
    if "Connected" in res.stdout:
        return True
    return False


def scan_target(ip, port, results):
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(0.5)
        result = s.connect_ex((ip, port))
        if result == 0:
            print(f"[+] OPEN: {ip}:{port}")
            results.append((ip, port))
        s.close()
    except:
        pass


def scanner():
    target_subnet = "192.168.1"
    ports = [445, 3389, 139, 80]

    threads = []
    results = []

    print(f"Scanning {target_subnet}.0/24...")

    for i in range(1, 255):
        ip = f"{target_subnet}.{i}"
        for port in ports:
            t = threading.Thread(target=scan_target, args=(ip, port, results))
            t.start()
            threads.append(t)

            # Limit concurrency
            if len(threads) >= 100:
                for t in threads:
                    t.join()
                threads = []

    for t in threads:
        t.join()

    return results


if __name__ == "__main__":
    if connect_warp():
        print("\nWARP Connected. Starting scan...")
        found = scanner()
        if found:
            print("\nFound open ports:")
            for ip, port in found:
                print(f"  {ip}:{port}")
        else:
            print("\nNo open ports found.")
    else:
        print("Failed to connect WARP")
