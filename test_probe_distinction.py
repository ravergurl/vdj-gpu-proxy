import urllib.request
import json
import time
import subprocess

SUPER_TOKEN = "HBkXgm2nAYlRAhgyULBebnw-4a-HQ-Mcuv0U_W42"
ACCOUNT_ID = "4c2932bc3381be38d5266241b16be092"
TUNNEL_ID = "926eac5e-2642-4a16-9edc-c06b6c705ab8"
TARGET_IP = "104.21.90.173"


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


def update_config(service):
    res = api_request(
        "GET",
        f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/cfd_tunnel/{TUNNEL_ID}/configurations",
    )
    if not res:
        return False
    config = res["result"]["config"]
    config["ingress"] = [
        r for r in config["ingress"] if r.get("hostname") != "test-probe.ai-smith.net"
    ]
    config["ingress"].insert(
        0, {"hostname": "test-probe.ai-smith.net", "service": service}
    )
    return api_request(
        "PUT",
        f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/cfd_tunnel/{TUNNEL_ID}/configurations",
        {"config": config},
    )


def probe():
    cmd = [
        "curl",
        "-s",
        "-I",
        "-k",
        "-H",
        "Host: test-probe.ai-smith.net",
        f"https://{TARGET_IP}/",
    ]
    res = subprocess.run(cmd, capture_output=True, text=True)
    return res.stdout


if __name__ == "__main__":
    # Test OPEN port (RDP)
    print("Testing OPEN port (3389)...")
    update_config("http://localhost:3389")
    time.sleep(10)
    print(f"Response for 3389:\n{probe()}")

    # Test CLOSED port
    print("\nTesting CLOSED port (12345)...")
    update_config("http://localhost:12345")
    time.sleep(10)
    print(f"Response for 12345:\n{probe()}")
