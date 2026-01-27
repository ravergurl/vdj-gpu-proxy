import urllib.request
import json

SUPER_TOKEN = "HBkXgm2nAYlRAhgyULBebnw-4a-HQ-Mcuv0U_W42"
ACCOUNT_ID = "4c2932bc3381be38d5266241b16be092"


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


def create_rdp_app():
    print("\n1. Creating Access App...")
    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/access/apps"
    payload = {
        "name": "sisyphus-rdp-access",
        "domain": "rdp.ai-smith.net",
        "type": "self_hosted",
        "session_duration": "24h",
    }
    return api_request("POST", url, payload)


def create_policy(app_id):
    print("\n2. Creating Access Policy...")
    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/access/apps/{app_id}/policies"
    payload = {
        "name": "allow-everyone",
        "decision": "allow",
        "include": [{"everyone": {}}],
    }
    return api_request("POST", url, payload)


def create_service_token():
    print("\n3. Creating Service Token...")
    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/access/service_tokens"
    payload = {"name": "sisyphus-rdp-token", "duration": "8760h"}
    return api_request("POST", url, payload)


def add_token_to_policy(app_id, policy_id, token_id):
    print("\n4. Adding Service Token to Policy...")
    # To add a Service Token to a policy, we update the policy to include it
    # We need to fetch the policy first or just overwrite "include"
    # Actually, we should add it as an "include" rule alongside "everyone" or instead of it?
    # Usually you want Service Token OR User.

    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/access/apps/{app_id}/policies/{policy_id}"
    payload = {
        "name": "allow-everyone-and-token",
        "decision": "allow",
        "include": [{"everyone": {}}, {"service_token": {"token_id": token_id}}],
    }
    return api_request("PUT", url, payload)


if __name__ == "__main__":
    # 1. Create App
    app_res = create_rdp_app()
    if not app_res or not app_res.get("success"):
        print("Failed to create app")
        exit(1)

    app_id = app_res["result"]["id"]
    print(f"App Created: {app_id}")

    # 2. Create Policy
    pol_res = create_policy(app_id)
    if not pol_res or not pol_res.get("success"):
        print("Failed to create policy")
        # continue anyway? No, need policy
        exit(1)

    policy_id = pol_res["result"]["id"]
    print(f"Policy Created: {policy_id}")

    # 3. Create Service Token
    token_res = create_service_token()
    if not token_res or not token_res.get("success"):
        print("Failed to create service token")
        exit(1)

    token_id = token_res["result"]["id"]
    client_id = token_res["result"]["client_id"]
    client_secret = token_res["result"]["client_secret"]
    print(f"Service Token Created: {token_id}")
    print(f"Client ID: {client_id}")
    print(f"Client Secret: {client_secret}")

    # 4. Update Policy to include Token
    # Wait, we created a policy that allows EVERYONE.
    # If we want to allow the Service Token specifically (for automated access), we should add it.
    # Cloudflare Access logic: Include A OR Include B.

    update_res = add_token_to_policy(app_id, policy_id, token_id)
    if update_res and update_res.get("success"):
        print("Policy updated to include service token")
    else:
        print("Failed to update policy")

    # Save credentials to file
    with open("rdp_access_creds.json", "w") as f:
        json.dump(
            {
                "app_id": app_id,
                "service_token_id": token_id,
                "client_id": client_id,
                "client_secret": client_secret,
            },
            f,
            indent=2,
        )
    print("\nCredentials saved to rdp_access_creds.json")
