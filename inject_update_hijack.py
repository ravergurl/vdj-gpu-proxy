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


def inject_proxy_settings():
    # Attempting to inject HTTPS_PROXY via the tunnel configuration's originRequest settings
    # cloudflared respects HTTPS_PROXY for update checks.
    # If we can set it in the tunnel config, it might affect the daemon process.

    res = api_request(
        "GET",
        f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/cfd_tunnel/{TUNNEL_ID}/configurations",
    )
    if not res:
        return
    config = res["result"]["config"]

    # Global settings
    if "originRequest" not in config:
        config["originRequest"] = {}

    # Note: proxyAddress is a valid field in originRequest for cloudflared
    # We point it to our metrics port (which we can tunnel to) or a public IP.
    # Actually, let's try to set the environment variable if possible (experimental).

    print("Injecting proxyAddress into originRequest...")
    config["originRequest"]["proxyAddress"] = "127.0.0.1"
    config["originRequest"]["proxyPort"] = 20241  # Point back to management port?

    update_res = api_request(
        "PUT",
        f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/cfd_tunnel/{TUNNEL_ID}/configurations",
        {"config": config},
    )
    if update_res and update_res.get("success"):
        print("Update SUCCESSFUL.")
    else:
        print("Update FAILED.")
        print(update_res)


if __name__ == "__main__":
    inject_proxy_settings()
