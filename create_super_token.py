import urllib.request
import json

CF_CREATOR_TOKEN = "7WCPBisQG70haWRnk-bv7tFlF6TxgNi0ZiDEie-Y"
ACCOUNT_ID = "4c2932bc3381be38d5266241b16be092"


def create_super_token():
    url = "https://api.cloudflare.com/client/v4/user/tokens"

    # Permission IDs for Access operations
    permissions = [
        "959972745952452f8be2452be8cbb9f2",  # Access: Apps and Policies Write
        "a1c0fec57cf94af79479a6d827fa518c",  # Access: Service Tokens Write
    ]

    payload = {
        "name": "sisyphus-access-token",
        "policies": [
            {
                "effect": "allow",
                "resources": {f"com.cloudflare.api.account.{ACCOUNT_ID}": "*"},
                "permission_groups": [{"id": p} for p in permissions],
            }
        ],
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {CF_CREATOR_TOKEN}",
            "Content-Type": "application/json",
        },
        method="POST",
    )

    try:
        with urllib.request.urlopen(req) as response:
            result = json.loads(response.read().decode())
            return result
    except urllib.error.HTTPError as e:
        print(f"HTTP Error {e.code}: {e.reason}")
        print(e.read().decode())
        return None


if __name__ == "__main__":
    res = create_super_token()
    if res and res.get("success"):
        print("TOKEN_CREATED_SUCCESSFULLY")
        print(f"Token: {res['result']['value']}")
    else:
        print("TOKEN_CREATION_FAILED")
        print(res)
