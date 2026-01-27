import json
import subprocess
import time


def check_mgmt_leak_detailed():
    try:
        with open("rdp_access_creds.json", "r") as f:
            creds = json.load(f)
    except:
        return

    client_id = creds["client_id"]
    client_secret = creds["client_secret"]

    target_hostname = "mgmt.scan.ai-smith.net"
    local_port = 20241

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
    time.sleep(20)

    # Check if process died
    if proc.poll() is not None:
        print("Tunnel process died:")
        print(proc.stderr.read().decode())
        return

    print("Tunnel process active. Probing endpoints...")

    endpoints = ["/metrics", "/config", "/ready", "/health"]

    for ep in endpoints:
        probe_cmd = ["curl", "-v", "--http1.1", f"http://127.0.0.1:{local_port}{ep}"]
        res = subprocess.run(probe_cmd, capture_output=True, text=True)
        if res.stdout:
            print(f"--- Data from {ep} ---")
            print(res.stdout[:1000])
        else:
            print(f"--- No data from {ep} ---")
            print(res.stderr[:500])

    proc.terminate()


if __name__ == "__main__":
    check_mgmt_leak_detailed()
