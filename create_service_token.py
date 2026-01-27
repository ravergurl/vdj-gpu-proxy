import urllib.request
import json

SUPER_TOKEN = "s0bYabENXVZy71Yx9RlbqE_M7iMNHfRk-gBq5Cce"
ACCOUNT_ID = "4c2932bc3381be38d5266241b16be092"


def create_service_token():
    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/access/service_tokens"

    payload = {"name": "sisyphus-service-token", "duration": "8760h"}

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {SUPER_TOKEN}",
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
    print("Creating Service Token...")
    result = create_service_token()
    if result and result.get("success"):
        print("SUCCESS: Service Token Created")
        print(f"Token: {result['result']['token']}")
        print(f"Name: {result['result']['name']}")
    else:
        print("FAILED to create Service Token")
        print(result)
