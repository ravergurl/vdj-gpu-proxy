import urllib.request
import json

SUPER_TOKEN = "HBkXgm2nAYlRAhgyULBebnw-4a-HQ-Mcuv0U_W42"
ACCOUNT_ID = "4c2932bc3381be38d5266241b16be092"


def test_token_permissions():
    tests = [
        (
            "Tunnel List",
            f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/cfd_tunnel",
        ),
        (
            "Teamnet Routes",
            f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/teamnet/routes",
        ),
        (
            "Access Apps",
            f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/access/apps",
        ),
        (
            "DNS Records",
            f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/access/apps",
        ),
    ]

    for test_name, url in tests:
        print(f"\nTesting {test_name}...")
        req = urllib.request.Request(
            url,
            headers={
                "Authorization": f"Bearer {SUPER_TOKEN}",
                "Content-Type": "application/json",
            },
            method="GET",
        )

        try:
            with urllib.request.urlopen(req) as response:
                result = json.loads(response.read().decode())
                if result.get("success"):
                    print(f"  [SUCCESS] {test_name}: OK")
                else:
                    print(f"  [ERROR] {test_name}: API Error - {result}")
        except urllib.error.HTTPError as e:
            if e.code == 403:
                print(f"  [FORBIDDEN] {test_name}: No permission")
            else:
                print(f"  [HTTP_ERROR] {test_name}: HTTP {e.code} - {e.reason}")
        except Exception as e:
            print(f"  [EXCEPTION] {test_name}: {e}")


if __name__ == "__main__":
    test_token_permissions()
