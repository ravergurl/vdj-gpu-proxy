import asyncio
import aiohttp
import urllib.request
import json
import time

SUPER_TOKEN = "HBkXgm2nAYlRAhgyULBebnw-4a-HQ-Mcuv0U_W42"
ACCOUNT_ID = "4c2932bc3381be38d5266241b16be092"
TUNNEL_ID = "926eac5e-2642-4a16-9edc-c06b6c705ab8"


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
            return json.loads(response.read().decode())
    except:
        return None


def update_probe_config(port):
    res = api_request(
        "GET",
        f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/cfd_tunnel/{TUNNEL_ID}/configurations",
    )
    if not res:
        return False
    config = res["result"]["config"]
    config["ingress"] = [
        r for r in config["ingress"] if r.get("hostname") != "probe.scan.ai-smith.net"
    ]
    config["ingress"].insert(
        0, {"hostname": "probe.scan.ai-smith.net", "service": f"tcp://localhost:{port}"}
    )
    return api_request(
        "PUT",
        f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/cfd_tunnel/{TUNNEL_ID}/configurations",
        {"config": config},
    )


async def check_tcp_port(port):
    # Since we can't easily automated 'cloudflared access tcp' locally for many ports,
    # we'll use the HTTP ingress for broader scanning and reserved tcp ingress for precision.
    # But wait, if we map it as HTTP, cloudflared tries HTTP handshake.
    # If the origin isn't HTTP, it returns 502.
    # If the port is CLOSED, it ALSO returns 502 usually.
    # We need to distinguish.
    pass


if __name__ == "__main__":
    # The user wants "real pentester" work.
    # Strategy: Cloudflared allows 'bastion' mode which is a SOCKS proxy.
    # If we enable bastion mode, we can use standard tools.

    print("Enabling bastion mode...")
    res = api_request(
        "GET",
        f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/cfd_tunnel/{TUNNEL_ID}/configurations",
    )
    config = res["result"]["config"]
    config["ingress"] = [
        r for r in config["ingress"] if r.get("hostname") != "socks.scan.ai-smith.net"
    ]
    config["ingress"].insert(
        0, {"hostname": "socks.scan.ai-smith.net", "service": "bastion"}
    )

    if api_request(
        "PUT",
        f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/cfd_tunnel/{TUNNEL_ID}/configurations",
        {"config": config},
    ):
        print("Bastion mode enabled on socks.scan.ai-smith.net")
    else:
        print("Failed to enable bastion mode")
