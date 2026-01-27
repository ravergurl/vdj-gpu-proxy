import json
import subprocess
import time
import socket
import os


def start_tunnel_and_test():
    # Load credentials
    try:
        with open("rdp_access_creds.json", "r") as f:
            creds = json.load(f)
    except FileNotFoundError:
        print("Credentials file not found!")
        return

    client_id = creds["client_id"]
    client_secret = creds["client_secret"]

    print(f"Starting tunnel for smb.ai-smith.net using Client ID: {client_id[:5]}...")

    # Start cloudflared
    # Note: Assuming cloudflared is in PATH
    cmd = [
        "cloudflared",
        "access",
        "tcp",
        "--hostname",
        "smb.ai-smith.net",
        "--url",
        "localhost:10445",
        "--id",
        client_id,
        "--secret",
        client_secret,
    ]

    # Use shell=True for windows if needed, but array usually safer
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    print("Waiting for tunnel to establish...")
    time.sleep(5)

    # Test connection
    print("Testing connection to localhost:10445...")
    try:
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.settimeout(2)
        result = s.connect_ex(("127.0.0.1", 10445))
        if result == 0:
            print("SUCCESS: Connected to SMB tunnel port 10445!")
            print("You can now attempt SMB authentication against 127.0.0.1:10445")
        else:
            print("FAILED: Port 10445 is not open. Tunnel might have failed.")
            # Check if process is dead
            if proc.poll() is not None:
                print("Cloudflared process exited.")
                out, err = proc.communicate()
                print(f"Stderr: {err.decode()}")
    except Exception as e:
        print(f"Error testing connection: {e}")

    # Don't kill it yet, we might want to use it
    # But for this script, we'll terminate to be clean
    proc.terminate()


if __name__ == "__main__":
    start_tunnel_and_test()
