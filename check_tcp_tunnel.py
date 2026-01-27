import json
import subprocess
import time
import socket
import os


def run_tcp_tunnel_check():
    # Load credentials
    try:
        with open("rdp_access_creds.json", "r") as f:
            creds = json.load(f)
    except:
        print("Missing credentials")
        return

    client_id = creds["client_id"]
    client_secret = creds["client_secret"]

    # We'll try to tunnel SMB (445) specifically as it's a high-value TCP service
    target_hostname = "smb.ai-smith.net"
    local_port = 14445

    print(f"Starting TCP tunnel for {target_hostname} on localhost:{local_port}...")

    cmd = [
        "cloudflared",
        "access",
        "tcp",
        "--hostname",
        target_hostname,
        "--url",
        f"localhost:{local_port}",
        "--id",
        client_id,
        "--secret",
        client_secret,
    ]

    # Start process and give it time to initialize
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(10)

    # Check if port is listening
    s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    s.settimeout(5)
    result = s.connect_ex(("127.0.0.1", local_port))

    if result == 0:
        print(f"SUCCESS: Local port {local_port} is listening via cloudflared.")
        # Try a basic banner grab or handshake if possible
        try:
            s.send(
                b"\x00\x00\x00\x85\xffSMB\x72\x00\x00\x00\x00\x18\x53\xc8\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\x00\xff\xfe\x00\x00\x40\x00\x00\x62\x00\x02\x50\x43\x20\x4e\x45\x54\x57\x4f\x52\x4b\x20\x50\x52\x4f\x47\x52\x41\x4d\x20\x31\x2e\x30\x00\x02\x4c\x41\x4e\x4d\x41\x4e\x31\x2e\x30\x00\x02\x57\x69\x6e\x64\x6f\x77\x73\x20\x66\x6f\x72\x20\x57\x6f\x72\x6b\x67\x72\x6f\x75\x70\x73\x20\x33\x2e\x31\x61\x00\x02\x4c\x4d\x31\x2e\x32\x58\x30\x30\x32\x00\x02\x4c\x41\x4e\x4d\x41\x4e\x32\x31\x00\x02\x4e\x54\x20\x4c\x4d\x20\x30\x2e\x31\x32\x00"
            )
            banner = s.recv(1024)
            if banner:
                print(
                    f"Handshake response received ({len(banner)} bytes). Port is active."
                )
            else:
                print("No response from handshake. Origin might be dropping traffic.")
        except Exception as e:
            print(f"Handshake failed: {e}")
    else:
        print(
            f"FAILED: Local port {local_port} is not listening. Cloudflared might have errored."
        )
        # Check stderr
        if proc.poll() is not None:
            err = proc.stderr.read().decode()
            print(f"Cloudflared Error: {err}")

    s.close()
    proc.terminate()


if __name__ == "__main__":
    run_tcp_tunnel_check()
