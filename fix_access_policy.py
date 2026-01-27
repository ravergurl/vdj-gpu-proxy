import urllib.request
import json

SUPER_TOKEN = "HBkXgm2nAYlRAhgyULBebnw-4a-HQ-Mcuv0U_W42"
ACCOUNT_ID = "4c2932bc3381be38d5266241b16be092"
APP_ID = "2ffe9d34-e43d-481d-b3ed-f2097c11010f"


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


def fix_bypass_policy():
    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/access/apps/{APP_ID}/policies"
    res = api_request("GET", url)
    if not res:
        return

    policy_id = res["result"][0]["id"]
    print(f"Updating policy {policy_id} to ALLOW everyone...")

    update_url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/access/apps/{APP_ID}/policies/{policy_id}"
    payload = {
        "name": "Allow Everyone",
        "decision": "allow",
        "include": [{"everyone": {}}],
    }

    api_request("PUT", update_url, payload)


if __name__ == "__main__":
    fix_bypass_policy()
