import urllib.request
import json

CF_TOKEN_TOKEN = "kV-M28zVHv14GwDUb48K8bEXEJ1jOriuWhdrn5ua"
ACCOUNT_ID = "4c2932bc3381be38d5266241b16be092"


def api_request(method, url, data=None):
    headers = {
        "Authorization": f"Bearer {CF_TOKEN_TOKEN}",
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
        print(f"HTTP Error {e.code}: {e.reason}")
        return None
    except Exception as e:
        print(f"Error: {e}")
        return None


# Try creating Cloudflare Access tokens
print("Creating Cloudflare Access tokens...")

# 1. Create a Service Token (for authentication)
service_token_data = {
    "name": "rdp-access-token",
    "duration": "8760h",  # 1 year
    "policies": {"dns": ["rdp.ai-smith.net"]},
}

result = api_request(
    "POST",
    "https://api.cloudflare.com/client/v4/accounts/4c2932bc3381be38d5266241b16be092/access/service_tokens",
    data=service_token_data,
)

if result and result.get("success"):
    token = result["result"]["token"]
    print(f"[+] Service Token created: {token}")
    print(f"    Name: {service_token_data['name']}")
    print(f"    Duration: {service_token_data['duration']}")
    print(f"    Policies: {service_token_data['policies']}")
else:
    print("[-] Failed to create service token")
    print(f"Error: {result}")
