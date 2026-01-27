import urllib.request
import json
import time
import subprocess

SUPER_TOKEN = "HBkXgm2nAYlRAhgyULBebnw-4a-HQ-Mcuv0U_W42"
ACCOUNT_ID = "4c2932bc3381be38d5266241b16be092"
TUNNEL_ID = "926eac5e-2642-4a16-9edc-c06b6c705ab8"
TARGET_IP = "104.21.90.173"  # Cloudflare Edge IP for metrics.ai-smith.net

PORTS = [20241, 80, 8080, 443, 3000, 5000, 8000, 5985, 135, 445, 3389, 22]


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
        print(f"API Error {e.code}: {e.reason}")
        return None


def get_current_config():
    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/cfd_tunnel/{TUNNEL_ID}/configurations"
    return api_request("GET", url)


def update_metrics_rule(target_service):
    # Get config
    res = get_current_config()
    if not res:
        return False

    config = res["result"]["config"]

    # Find metrics rule and update it, or add it
    found = False
    for rule in config["ingress"]:
        if rule.get("hostname") == "metrics.ai-smith.net":
            rule["service"] = target_service
            found = True
            break

    if not found:
        config["ingress"].insert(
            0, {"hostname": "metrics.ai-smith.net", "service": target_service}
        )

    # Push update
    url = f"https://api.cloudflare.com/client/v4/accounts/{ACCOUNT_ID}/cfd_tunnel/{TUNNEL_ID}/configurations"
    res = api_request("PUT", url, {"config": config})
    return res and res.get("success")


def check_endpoint():
    # Curl with Host header
    # We use subprocess because urllib might not handle the SSL/Host trick easily without context
    cmd = [
        "curl",
        "-s",
        "-I",
        "-k",
        "-H",
        "Host: metrics.ai-smith.net",
        "--connect-timeout",
        "5",
        f"https://{TARGET_IP}/",
    ]
    try:
        res = subprocess.run(cmd, capture_output=True, text=True)
        return res.stdout
    except:
        return ""


if __name__ == "__main__":
    print("Starting Tunnel Port Scan via metrics.ai-smith.net...")

    for port in PORTS:
        target = f"http://localhost:{port}"
        print(f"\n[+] Mapping metrics.ai-smith.net -> {target}")

        if update_metrics_rule(target):
            print("    Config updated. Waiting 5s for propagation...")
            time.sleep(5)

            output = check_endpoint()
            # Analyze output
            if "HTTP/2 200" in output or "HTTP/1.1 200" in output:
                print(f"    !!! PORT {port} IS OPEN and returning 200 OK !!!")
                print(output)
            elif "502 Bad Gateway" in output:
                print(f"    [-] Port {port} seems CLOSED (502 from Cloudflare)")
            elif "503 Service Unavailable" in output:
                print(f"    [-] Port {port} TIMEOUT/UNAVAILABLE")
            elif "404 Not Found" in output:
                print(f"    [!] Port {port} OPEN (404 Not Found) - Service running!")
            elif "401 Unauthorized" in output or "403 Forbidden" in output:
                print(f"    [!] Port {port} OPEN (Auth Required) - Service running!")
            else:
                print(f"    [?] Unknown response for {port}:")
                print(output.split("\n")[0])
        else:
            print("    Failed to update config")
