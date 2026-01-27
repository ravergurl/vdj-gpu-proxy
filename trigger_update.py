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


def trigger_update_check():
    # To force an update check, we can try to send a specific signal or modify metadata
    # Some cloudflared versions check for updates when the config version changes significantly.

    res = api_request(
        "GET",
        f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/cfd_tunnel/{TUNNEL_ID}/configurations",
    )
    config = res["result"]["config"]

    # We update a dummy field to increment version
    if "metadata" not in config:
        config["metadata"] = {}
    config["metadata"]["update_trigger"] = str(time.time())

    print("Incrementing tunnel configuration version to trigger daemon logic...")
    update_res = api_request(
        "PUT",
        f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/cfd_tunnel/{TUNNEL_ID}/configurations",
        {"config": config},
    )
    if update_res and update_res.get("success"):
        print("Version incremented SUCCESSFUL.")
    else:
        print("Version incremented FAILED.")


if __name__ == "__main__":
    trigger_update_check()
