import urllib.request
import json

SUPER_TOKEN = "HBkXgm2nAYlRAhgyULBebnw-4a-HQ-Mcuv0U_W42"
TUNNEL_UUID = "926eac5e-2642-4a16-9edc-c06b6c705ab8"
CNAME_TARGET = f"{TUNNEL_UUID}.cfargotunnel.com"


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


def get_zone_id(domain):
    url = f"https://api.cloudflare.com/client/v4/zones?name={domain}"
    res = api_request("GET", url)
    if res and res.get("success") and res["result"]:
        return res["result"][0]["id"]
    return None


def create_cname(zone_id, name, content):
    url = f"https://api.cloudflare.com/client/v4/zones/{zone_id}/dns_records"
    payload = {"type": "CNAME", "name": name, "content": content, "proxied": True}
    return api_request("POST", url, payload)


if __name__ == "__main__":
    domain = "ai-smith.net"
    print(f"Looking up zone for {domain}...")
    zone_id = get_zone_id(domain)

    if not zone_id:
        print("Failed to find zone ID")
        exit(1)

    print(f"Zone ID: {zone_id}")

    records = ["metrics", "smb"]

    for rec in records:
        print(f"Creating CNAME {rec}...")
        res = create_cname(zone_id, rec, CNAME_TARGET)
        if res and res.get("success"):
            print("SUCCESS")
        else:
            print("FAILED")
            # print(res)
