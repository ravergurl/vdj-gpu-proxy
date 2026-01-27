import urllib.request
import json
import time

CF_CREATOR_TOKEN = "7WCPBisQG70haWRnk-bv7tFlF6TxgNi0ZiDEie-Y"
ACCOUNT_ID = "4c2932bc3381be38d5266241b16be092"


def api_request(method, url, data=None):
    headers = {
        "Authorization": f"Bearer {CF_CREATOR_TOKEN}",
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


def cleanup_tokens():
    print("Cleaning up old sisyphus tokens...")
    result = api_request("GET", "https://api.cloudflare.com/client/v4/user/tokens")
    if result and result.get("success"):
        for token in result["result"]:
            if token["name"].startswith("sisyphus-"):
                print(f"Deleting {token['name']} ({token['id']})...")
                api_request(
                    "DELETE",
                    f"https://api.cloudflare.com/client/v4/user/tokens/{token['id']}",
                )
    else:
        print("Failed to list tokens for cleanup")


def create_correct_token():
    url = "https://api.cloudflare.com/client/v4/user/tokens"

    account_permissions = [
        {
            "id": "1e13c5124ca64b72b1969a67e8829049"
        },  # Access: Apps and Policies Write (ACCOUNT)
        {"id": "a1c0fec57cf94af79479a6d827fa518c"},  # Access: Service Tokens Write
        {"id": "1af1fa2adc104452b74a9a3364202f20"},  # Account Settings Write
        {"id": "c07321b023e944ff818fec44d8203567"},  # Cloudflare Tunnel Write
        {"id": "b33f02c6f7284e05a6f20741c0bb0567"},  # Zero Trust Write
    ]

    zone_permissions = [
        {"id": "4755a26eedb94da69e1066d98aa820be"}  # DNS Write (ZONE)
    ]

    payload = {
        "name": "sisyphus-super-token-final",
        "policies": [
            {
                "effect": "allow",
                "resources": {f"com.cloudflare.api.account.{ACCOUNT_ID}": "*"},
                "permission_groups": account_permissions,
            },
            {
                "effect": "allow",
                "resources": {f"com.cloudflare.api.account.zone.*": "*"},
                "permission_groups": zone_permissions,
            },
        ],
    }

    print("\nCreating new Super Token with correct scopes...")
    return api_request("POST", url, data=payload)


if __name__ == "__main__":
    cleanup_tokens()
    time.sleep(2)
    res = create_correct_token()
    if res and res.get("success"):
        print("\nSUCCESS: Token Created!")
        print(f"Token: {res['result']['value']}")
    else:
        print("\nFAILED to create token")
        print(res)
