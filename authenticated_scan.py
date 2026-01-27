import asyncio
import aiohttp
import urllib.request
import json
import time
import subprocess

SUPER_TOKEN = "HBkXgm2nAYlRAhgyULBebnw-4a-HQ-Mcuv0U_W42"
ACCOUNT_ID = "4c2932bc3381be38d5266241b16be092"
TUNNEL_ID = "926eac5e-2642-4a16-9edc-c06b6c705ab8"


def get_access_creds():
    try:
        with open("rdp_access_creds.json", "r") as f:
            return json.load(f)
    except:
        return None


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


def update_config(ports):
    res = api_request(
        "GET",
        f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/cfd_tunnel/{TUNNEL_ID}/configurations",
    )
    if not res:
        return False
    config = res["result"]["config"]

    # Keep existing non-scan rules
    config["ingress"] = [
        r for r in config["ingress"] if "scan.ai-smith.net" not in r.get("hostname", "")
    ]

    # Add scan rules
    for port in ports:
        config["ingress"].insert(
            0,
            {
                "hostname": f"{port}.scan.ai-smith.net",
                "service": f"http://localhost:{port}",
            },
        )

    return api_request(
        "PUT",
        f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/cfd_tunnel/{TUNNEL_ID}/configurations",
        {"config": config},
    )


async def probe_port(session, port, creds):
    hostname = f"{port}.scan.ai-smith.net"
    url = f"https://{hostname}/"

    try:
        async with session.get(url, ssl=False, timeout=10) as resp:
            # 502/503 = Error communicating with origin
            # 200/404/403/401 = Origin reached!
            if resp.status not in [502, 503, 504]:
                return port, resp.status, "OPEN"
            else:
                return port, resp.status, "CLOSED"
    except Exception as e:
        return port, 0, str(e)


async def main():
    creds = get_access_creds()
    if not creds:
        print("No Access credentials found")
        return

    # Scan high-value ports
    ports_to_scan = [22, 80, 443, 445, 3389, 5985, 20241, 8080, 3000, 5000]

    print(f"Updating config for ports: {ports_to_scan}")
    if update_config(ports_to_scan):
        print("Waiting 15s for propagation...")
        await asyncio.sleep(15)

        async with aiohttp.ClientSession() as session:
            tasks = [probe_port(session, p, creds) for p in ports_to_scan]
            results = await asyncio.gather(*tasks)

            for port, status, state in results:
                if state == "OPEN":
                    print(f"!!! PORT {port} IS OPEN (Status: {status}) !!!")
                else:
                    print(f"Port {port} is {state} (Status: {status})")
    else:
        print("Failed to update config")


if __name__ == "__main__":
    asyncio.run(main())
