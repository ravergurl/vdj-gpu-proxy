import json
import subprocess
import time
import os


def check_mgmt_detailed():
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

    # Check if process is alive
    if proc.poll() is not None:
        print("Tunnel process died.")
        return

    print("Tunnel process active. Checking for leaked state...")

    # Critical diagnostic paths discovered in research
    endpoints = [
        "/debug/pprof/goroutine?debug=2",
        "/config",
        "/diag/configuration",
        "/diag/tunnel",
        "/diag/system",
    ]

    for ep in endpoints:
        print(f"--- Endpoint: {ep} ---")
        probe_cmd = ["curl", "-v", "--http1.1", f"http://127.0.0.1:{local_port}{ep}"]
        res = subprocess.run(probe_cmd, capture_output=True, text=True)
        if res.stdout:
            print(f"STDOUT: {res.stdout[:500]}")
            # Save if significant
            if len(res.stdout) > 100:
                filename = (
                    ep.replace("/", "_").replace("?", "_").replace("=", "_") + ".log"
                )
                with open(filename, "w") as f:
                    f.write(res.stdout)
                print(f"Saved to {filename}")
        else:
            print(f"STDERR: {res.stderr[:200]}")

    proc.terminate()


if __name__ == "__main__":
    check_mgmt_detailed()
