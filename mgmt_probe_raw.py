import json
import subprocess
import time
import os


def probe_mgmt_raw():
    try:
        with open("rdp_access_creds.json", "r") as f:
            creds = json.load(f)
    except:
        print("Missing credentials")
        return

    client_id = creds["client_id"]
    client_secret = creds["client_secret"]

    target_hostname = "mgmt.scan.ai-smith.net"
    local_port = 20242  # Use a different local port

    print(f"Connecting to management port {target_hostname}...")

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

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(15)

    if proc.poll() is not None:
        print("Proxy died.")
        return

    print("Probing endpoints with raw socket...")
    # Some cloudflared versions might require specific headers or HTTP/2
    endpoints = ["/metrics", "/debug/pprof/", "/ready", "/health"]

    for ep in endpoints:
        try:
            # Use curl but force HTTP/1.1 and keep-alive
            probe_cmd = [
                "curl",
                "-v",
                "--http1.1",
                "-H",
                "Connection: keep-alive",
                f"http://127.0.0.1:{local_port}{ep}",
            ]
            res = subprocess.run(probe_cmd, capture_output=True, text=True)
            print(f"--- Endpoint: {ep} ---")
            print(f"Stdout: {res.stdout[:500]}")
            print(f"Stderr: {res.stderr[:500]}")
        except Exception as e:
            print(f"Error on {ep}: {e}")

    proc.terminate()


if __name__ == "__main__":
    probe_mgmt_raw()
