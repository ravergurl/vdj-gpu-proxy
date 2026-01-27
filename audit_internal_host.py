import asyncio
import aiohttp
import urllib.request
import json
import time

SUPER_TOKEN = "HBkXgm2nAYlRAhgyULBebnw-4a-HQ-Mcuv0U_W42"
ACCOUNT_ID = "4c2932bc3381be38d5266241b16be092"
TUNNEL_ID = "926eac5e-2642-4a16-9edc-c06b6c705ab8"
TARGET_IP = "104.21.90.173"
INTERNAL_IP = "192.168.1.160"


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
    except Exception as e:
        print(f"API Error: {e}")
        return None


def update_config_for_internal(ports):
    res = api_request(
        "GET",
        f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/cfd_tunnel/{TUNNEL_ID}/configurations",
    )
    if not res:
        return False
    config = res["result"]["config"]

    config["ingress"] = [
        r for r in config["ingress"] if "scan.ai-smith.net" not in r.get("hostname", "")
    ]

    for port in ports:
        config["ingress"].insert(
            0,
            {
                "hostname": f"int-{port}.scan.ai-smith.net",
                "service": f"http://{INTERNAL_IP}:{port}",
            },
        )

    return api_request(
        "PUT",
        f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/cfd_tunnel/{TUNNEL_ID}/configurations",
        {"config": config},
    )


async def probe_internal_port(session, port, creds):
    hostname = f"int-{port}.scan.ai-smith.net"
    headers = {
        "Host": hostname,
        "CF-Access-Client-Id": creds["client_id"],
        "CF-Access-Client-Secret": creds["client_secret"],
    }
    url = f"https://rdp.ai-smith.net/"

    try:
        async with session.get(url, headers=headers, ssl=False, timeout=10) as resp:
            # 502 = Connection Refused (Port Closed)
            # 504 = Gateway Timeout (Port Filtered/Non-Responsive)
            # 200/404/403/401 = Port Open (Service Reached)
            if resp.status not in [502, 503, 504]:
                return port, resp.status, "OPEN"
            else:
                return port, resp.status, "CLOSED/FILTERED"
    except Exception as e:
        return port, 0, str(e)


async def main():
    creds = get_access_creds()
    if not creds:
        print("Access credentials missing")
        return

    ports_to_audit = [80, 443, 445, 3389, 5985, 5986, 135, 139]
    print(f"Auditing Internal IP {INTERNAL_IP} via Tunnel redirection...")

    if update_config_for_internal(ports_to_audit):
        print("Propagating config (15s)...")
        await asyncio.sleep(15)

        async with aiohttp.ClientSession() as session:
            tasks = [probe_internal_port(session, p, creds) for p in ports_to_audit]
            results = await asyncio.gather(*tasks)

            print(f"\nAudit Results for {INTERNAL_IP}:")
            for port, status, state in results:
                if state == "OPEN":
                    print(f"[!] {INTERNAL_IP}:{port} - {state} (Status: {status})")
                else:
                    print(f"[-] {INTERNAL_IP}:{port} - {state} (Status: {status})")
    else:
        print("Config update failed")


if __name__ == "__main__":
    asyncio.run(main())
