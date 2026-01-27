import asyncio
import aiohttp
import urllib.request
import json
import time
import sys

SUPER_TOKEN = "HBkXgm2nAYlRAhgyULBebnw-4a-HQ-Mcuv0U_W42"
ACCOUNT_ID = "4c2932bc3381be38d5266241b16be092"
TUNNEL_ID = "926eac5e-2642-4a16-9edc-c06b6c705ab8"
TARGET_IP = "104.21.90.173"  # Cloudflare Edge

# Top ports + specific ones
PORTS = [
    21,
    22,
    23,
    25,
    53,
    80,
    81,
    110,
    111,
    135,
    139,
    143,
    443,
    445,
    465,
    587,
    993,
    995,
    1433,
    1521,
    1723,
    2049,
    2082,
    2083,
    2086,
    2087,
    2095,
    2096,
    2222,
    3000,
    3128,
    3306,
    3389,
    3690,
    4444,
    5000,
    5432,
    5555,
    5800,
    5900,
    5985,
    5986,
    6000,
    6001,
    6379,
    6667,
    8000,
    8001,
    8008,
    8080,
    8081,
    8443,
    8888,
    9000,
    9090,
    9418,
    9999,
    10000,
    20241,
    27017,
    27018,
]

BATCH_SIZE = 20


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
    except Exception as e:
        print(f"API Error: {e}")
        return None


def get_config():
    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/cfd_tunnel/{TUNNEL_ID}/configurations"
    return api_request("GET", url)


def update_config(config):
    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/cfd_tunnel/{TUNNEL_ID}/configurations"
    return api_request("PUT", url, {"config": config})


async def check_port(session, port):
    hostname = f"{port}.scan.ai-smith.net"
    url = f"https://{TARGET_IP}/"
    headers = {"Host": hostname}

    try:
        # Disable SSL verification for speed and because IP access mismatches cert
        async with session.get(url, headers=headers, ssl=False, timeout=5) as response:
            status = response.status
            # 502 = Connection Refused at origin
            # 503 = Origin unreachable
            if status not in [502, 503, 504]:
                return port, status, "OPEN"
            else:
                return port, status, "CLOSED"
    except Exception as e:
        return port, 0, str(e)


async def scan_batch(ports):
    # 1. Update Config
    print(f"  > Configuring ingress for ports: {ports}")
    res = get_config()
    if not res:
        return

    config = res["result"]["config"]

    # Filter safely: Keep if (no hostname key) OR (scan.ai-smith.net not in hostname)
    config["ingress"] = [
        r
        for r in config["ingress"]
        if "hostname" not in r or "scan.ai-smith.net" not in r["hostname"]
    ]

    # Add new rules
    new_rules = []
    for port in ports:
        new_rules.append(
            {
                "hostname": f"{port}.scan.ai-smith.net",
                "service": f"http://localhost:{port}",
            }
        )

    # Insert at top
    for r in reversed(new_rules):
        config["ingress"].insert(0, r)

    if not update_config(config):
        print("  ! Failed to update config")
        return

    print("  > Waiting 5s for propagation...")
    await asyncio.sleep(5)

    # 2. Scan
    print("  > Probing...")
    async with aiohttp.ClientSession() as session:
        tasks = [check_port(session, p) for p in ports]
        results = await asyncio.gather(*tasks)

        for port, status, state in results:
            if state == "OPEN":
                print(f"    [+] PORT {port} OPEN (Status: {status})")


async def main():
    print(f"Starting Batch Scan of {len(PORTS)} ports...")

    # Split into batches
    for i in range(0, len(PORTS), BATCH_SIZE):
        batch = PORTS[i : i + BATCH_SIZE]
        print(f"\nBatch {i // BATCH_SIZE + 1}: Scanning {batch}")
        await scan_batch(batch)

    print("\nScan Complete.")


if __name__ == "__main__":
    asyncio.run(main())
