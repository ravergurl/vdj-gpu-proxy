import urllib.request
import json

CF_API_TOKEN = "ySIb_2uMzHQDvnK5MulcCvOiRKsC6k0pH188bG8Y"
ACCOUNT_ID = "4c2932bc3381be38d5266241b16be092"
TUNNEL_ID = "926eac5e-2642-4a16-9edc-c06b6c705ab8"
VIRTUAL_NETWORK_ID = "e90ee4ca-34aa-4c84-a512-9ca8f22a56a9"


def api_request(method, url, data=None):
    req = urllib.request.Request(
        url,
        data=json.dumps(data).encode() if data else None,
        headers={
            "Authorization": f"Bearer {CF_API_TOKEN}",
            "Content-Type": "application/json",
        },
        method=method,
    )
    with urllib.request.urlopen(req, timeout=30) as response:
        body = response.read().decode()
        return json.loads(body)


def get_tunnel_config():
    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/cfd_tunnel/{TUNNEL_ID}/configurations"
    return api_request("GET", url)


def update_tunnel_config(new_config):
    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/cfd_tunnel/{TUNNEL_ID}/configurations"
    result = api_request("PUT", url, data=new_config)
    return result


def add_route_to_virtual_network(network_name):
    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/teamnet/virtual_networks/{VIRTUAL_NETWORK_ID}/routes"
    data = {"network": network_name}
    result = api_request("POST", url, data=data)
    return result


if __name__ == "__main__":
    import sys

    # Current config
    current = get_tunnel_config()
    print("Current config:")
    print(json.dumps(current["result"]["config"], indent=2))

    # Strategy: Add route from WARP to virtual network
    # This might enable bidirectional access
    print("\nAttempting to add route from WARP client network...")
    result = add_route_to_virtual_network(VIRTUAL_NETWORK_ID)
    print(f"Result: {json.dumps(result, indent=2)}")

    if result["success"]:
        print("\nSuccess! Route added from WARP to Kalvin virtual network.")
        print("This should enable traffic flow between WARP and tunnel.")
