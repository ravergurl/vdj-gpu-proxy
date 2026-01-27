import urllib.request
import json

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
            result = json.loads(response.read().decode())
            return result
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.reason}")
        print(e.read().decode())
        return None


def get_current_config():
    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/cfd_tunnel/{TUNNEL_ID}/configurations"
    return api_request("GET", url)


def add_smb_ingress():
    config_res = get_current_config()
    if not config_res or not config_res.get("success"):
        print("Failed to get config")
        return

    config = config_res["result"]["config"]
    ingress = config["ingress"]

    # Check if already exists
    for rule in ingress:
        if rule.get("hostname") == "smb.ai-smith.net":
            print("SMB rule already exists")
            return

    # Insert new rule at the top
    new_rule = {"hostname": "smb.ai-smith.net", "service": "tcp://localhost:445"}
    ingress.insert(0, new_rule)

    # Update config
    print("Updating tunnel configuration...")
    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/cfd_tunnel/{TUNNEL_ID}/configurations"
    res = api_request("PUT", url, {"config": config})

    if res and res.get("success"):
        print("SUCCESS: Added smb.ai-smith.net -> localhost:445")
    else:
        print("FAILED to update config")
        print(res)


if __name__ == "__main__":
    add_smb_ingress()
