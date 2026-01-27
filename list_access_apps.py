import urllib.request
import json

ORIGINAL_TOKEN = "ySIb_2uMzHQDvnK5MulcCvOiRKsC6k0pH188bG8Y"
ACCOUNT_ID = "4c2932bc3381be38d5266241b16be092"


def list_access_apps():
    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/access/apps"

    req = urllib.request.Request(
        url,
        headers={
            "Authorization": f"Bearer {ORIGINAL_TOKEN}",
            "Content-Type": "application/json",
        },
        method="GET",
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
    print("Listing Access Apps...")
    result = list_access_apps()
    if result and result.get("success"):
        print("SUCCESS: Access Apps Listed")
        for app in result["result"]:
            print(f"  - {app['name']}: {app['id']} ({app['domain']})")
    else:
        print("FAILED to list Access Apps")
        print(result)
