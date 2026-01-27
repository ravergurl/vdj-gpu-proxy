import requests
import json

CF_API_TOKEN = "ySIb_2uMzHQDvnK5MulcCvOiRKsC6k0pH188bG8Y"
ACCOUNT_ID = "4c2932bc3381be38d5266241b16be092"
TUNNEL_ID = "926eac5e-2642-4a16-9edc-c06b6c705ab8"

# Get current config
headers = {
    "Authorization": f"Bearer {CF_API_TOKEN}",
    "Content-Type": "application/json",
}


def get_current_config():
    resp = requests.get(
        f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/cfd_tunnel/{TUNNEL_ID}/configurations",
        headers=headers,
    )
    return resp.json()


def update_config(new_config):
    resp = requests.put(
        f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/cfd_tunnel/{TUNNEL_ID}/configurations",
        headers=headers,
        data=json.dumps(new_config),
    )
    return resp.json()


def get_routes():
    resp = requests.get(
        f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/teamnet/routes",
        headers=headers,
    )
    return resp.json()


def add_route(network, tunnel_id, comment=""):
    resp = requests.post(
        f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/teamnet/routes",
        headers=headers,
        data=json.dumps(
            {"network": network, "tunnel_id": tunnel_id, "comment": comment}
        ),
    )
    return resp.json()


def get_virtual_networks():
    resp = requests.get(
        f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/teamnet/virtual_networks",
        headers=headers,
    )
    return resp.json()


if __name__ == "__main__":
    import sys

    current = get_current_config()
    print("Current config:")
    print(json.dumps(current["result"]["config"], indent=2))

    # Try adding a route to localhost:33890 (alternate RDP)
    print("\nAttempting to add route 10.200.1.0/24 -> localhost:33890...")
    result = add_route("10.200.1.0/24", TUNNEL_ID, "Alternative RDP route")
    print(f"Result: {json.dumps(result, indent=2)}")

    # Get all virtual networks
    print("\nVirtual networks:")
    vn = get_virtual_networks()
    for net in vn["result"]:
        print(f"  - {net['name']}: {net.get('comment', 'no comment')}")
