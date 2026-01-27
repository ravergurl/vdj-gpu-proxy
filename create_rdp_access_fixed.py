import urllib.request
import json

ORIGINAL_TOKEN = "HBkXgm2nAYlRAhgyULBebnw-4a-HQ-Mcuv0U_W42"
ACCOUNT_ID = "4c2932bc3381be38d5266241b16be092"


def create_rdp_access_app():
    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/access/apps"

    payload = {
        "name": "sisyphus-rdp-access",
        "domain": "rdp.ai-smith.net",
        "type": "rdp",
        "session_duration": "24h",
        "auto_redirect_to_identity": False,
        "policies": [
            {"name": "allow-anyone", "decision": "allow", "include": [{"everyone": {}}]}
        ],
    }

    req = urllib.request.Request(
        url,
        data=json.dumps(payload).encode(),
        headers={
            "Authorization": f"Bearer {ORIGINAL_TOKEN}",
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
        return None


if __name__ == "__main__":
    print("Creating RDP Access App...")
    result = create_rdp_access_app()
    if result and result.get("success"):
        print("SUCCESS: RDP Access App Created")
        print(f"App ID: {result['result']['id']}")
        print(f"Domain: {result['result']['domain']}")
        print(f"Type: {result['result']['type']}")
    else:
        print("FAILED to create RDP Access App")
        print(result)

        print("\nListing existing apps...")
        list_result = list_access_apps()
        if list_result and list_result.get("success"):
            print("Existing apps:")
            for app in list_result["result"]:
                print(f"  - {app['name']}: {app['id']} ({app['domain']})")
        else:
            print("Could not list apps")
