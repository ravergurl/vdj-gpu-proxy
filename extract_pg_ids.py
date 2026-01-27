import json

with open("permission_groups.json", "r") as f:
    groups = json.load(f)

targets = [
    "Cloudflare Tunnel Read",
    "Cloudflare Tunnel Write",
    "Access: Apps and Policies Write",
    "Access: Service Tokens Write",
    "Zero Trust Write",
    "Account Settings Write",
    "Account API Tokens Write",
    "Cloudflare One connectors Write",  # From grep: Grants write access to Cloudflare One connectors
    "Cloudflare One routes, subnets, and virtual networks Write",
]

results = []
for g in groups:
    if g["name"] in targets:
        results.append({"id": g["id"], "name": g["name"]})

print(json.dumps(results, indent=2))
