import subprocess
import time
import socket
import json


def get_creds():
    with open("rdp_access_creds.json", "r") as f:
        return json.load(f)


def run_mgmt_probe():
    creds = get_creds()
    cmd = [
        "cloudflared",
        "access",
        "tcp",
        "--hostname",
        "mgmt.scan.ai-smith.net",
        "--url",
        "localhost:20241",
        "--id",
        creds["client_id"],
        "--secret",
        creds["client_secret"],
    ]

    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    time.sleep(15)

    # Check if process is still running
    if proc.poll() is not None:
        print("Cloudflared process died:")
        print(proc.stderr.read().decode())
        return

    print("Tunnel process running. Checking logs...")
    # Read some stderr
    import os

    os.set_blocking(proc.stderr.fileno(), False)
    logs = proc.stderr.read()
    if logs:
        print(logs.decode())

    paths = ["/metrics", "/config", "/debug/pprof/", "/ready", "/health"]
    results = {}

    for p in paths:
        try:
            curl_cmd = ["curl", "-s", f"http://127.0.0.1:20241{p}"]
            res = subprocess.run(curl_cmd, capture_output=True, text=True)
            results[p] = res.stdout[:500]
        except Exception as e:
            results[p] = str(e)

    print(json.dumps(results, indent=2))
    proc.terminate()


if __name__ == "__main__":
    run_mgmt_probe()
