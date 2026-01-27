import urllib.request
import json

CF_TOKEN = "ySIb_2uMzHQDvnK5MulcCvOiRKsC6k0pH188bG8Y"


def api_request(method, url, data=None):
    headers = {
        "Authorization": f"Bearer {CF_TOKEN}",
        "Content-Type": "application/json",
    }
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode() if data else None,
        headers=headers,
        method=method,
    )
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            body = response.read().decode()
            return json.loads(body)
    except urllib.error.HTTPError as e:
        print(f"HTTP Error: {e.code} - {e.reason}")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None


# Check what account/team this token belongs to
print("Checking token permissions...")
result = api_request("GET", "https://api.cloudflare.com/client/v4/user/tokens/verify")
print(f"Result: {json.dumps(result, indent=2)}")

# Try to get access applications
print("\nChecking Access permissions...")
result = api_request(
    "GET",
    "https://api.cloudflare.com/client/v4/accounts/4c2932bc3381be38d5266241b16be092/access/apps",
)
print(f"Result: {json.dumps(result, indent=2)}")
