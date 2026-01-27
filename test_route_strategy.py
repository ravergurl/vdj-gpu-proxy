import urllib.request
import json

CF_API_TOKEN = "ySIb_2uMzHQDvnK5MulcCvOiRKsC6k0pH188bG8Y"
ACCOUNT_ID = "4c2932bc3381be38d5266241b16be092"
TUNNEL_ID = "926eac5e-2642-4a16-9edc-c06b6c705ab8"


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

    with urllib.request.urlopen(req) as response:
        body = response.read().decode()
        return json.loads(body)


def get_current_config():
    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/cfd_tunnel/{TUNNEL_ID}/configurations"
    result = api_request("GET", url)
    print("Current config:")
    print(json.dumps(result["result"]["config"], indent=2))
    return result


def update_config(new_config):
    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/cfd_tunnel/{TUNNEL_ID}/configurations"
    result = api_request("PUT", url, data=new_config)
    print(f"Result: {json.dumps(result, indent=2)}")
    return result


def get_routes():
    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/teamnet/routes"
    result = api_request("GET", url)
    print("\nAll routes:")
    print(json.dumps(result["result"], indent=2))
    return result


def add_route(network, tunnel_id, comment=""):
    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/teamnet/routes"
    data = {"network": network, "tunnel_id": tunnel_id, "comment": comment}
    result = api_request("POST", url, data=data)
    print(f"Result: {json.dumps(result, indent=2)}")
    return result


def get_virtual_networks():
    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/teamnet/virtual_networks"
    result = api_request("GET", url)
    print("\nVirtual networks:")
    for net in result["result"]:
        print(f"  - {net['name']}: {net.get('comment', 'no comment')}")
    return result


if __name__ == "__main__":
    import sys

    # Current ingress rules
    current = get_current_config()
    print(f"\nIngress count: {current['result']['config']['ingress'].__len__()}")

    # Try strategy 1: Add route for localhost:33890 (alternate RDP)
    print("\n\n=== STRATEGY 1: Route 10.200.1.0/24 to localhost:33890 ===")
    result = add_route("10.200.1.0/24", TUNNEL_ID, "Alternate RDP port")

    # Try strategy 2: Add route for 127.0.0.0/8 to access other services
    print("\n\n=== STRATEGY 2: Route 127.0.0.0/8 for local access ===")
    result = add_route("127.0.0.0/8", TUNNEL_ID, "Local services access")
