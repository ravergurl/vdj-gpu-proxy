import json
import subprocess
import time
import socket
import os


def run_mgmt_proxy():
    try:
        with open("rdp_access_creds.json", "r") as f:
            creds = json.load(f)
    except:
        print("Missing credentials")
        return

    client_id = creds["client_id"]
    client_secret = creds["client_secret"]

    # Target hostname we just set up in update_exploit_config.py
    target_hostname = "mgmt.scan.ai-smith.net"
    local_port = 20241

    print(f"Proxying {target_hostname} to localhost:{local_port}...")

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

    # Run in background
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)

    # Give it time to establish
    time.sleep(10)

    # Check if process is still alive
    if proc.poll() is not None:
        print("Proxy process died immediately.")
        print(proc.stderr.read().decode())
        return

    print("Proxy active. Probing endpoints...")

    # Common cloudflared management endpoints
    endpoints = ["/metrics", "/config", "/debug/pprof/", "/ready", "/health"]
    results = {}

    for ep in endpoints:
        try:
            # Use curl to probe the local side of the proxy
            probe_cmd = ["curl", "-s", "-m", "5", f"http://127.0.0.1:{local_port}{ep}"]
            res = subprocess.run(probe_cmd, capture_output=True, text=True)
            if res.stdout:
                results[ep] = {
                    "status": "OPEN",
                    "data_len": len(res.stdout),
                    "preview": res.stdout[:200],
                }
            else:
                results[ep] = {"status": "EMPTY", "stderr": res.stderr}
        except Exception as e:
            results[ep] = {"status": "ERROR", "msg": str(e)}

    print(json.dumps(results, indent=2))

    # Keep some logs if available
    os.set_blocking(proc.stderr.fileno(), False)
    logs = proc.stderr.read()
    if logs:
        print("\nProxy Logs:")
        print(logs.decode())

    proc.terminate()


if __name__ == "__main__":
    run_mgmt_proxy()
