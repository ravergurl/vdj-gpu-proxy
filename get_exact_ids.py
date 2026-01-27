import json

with open("permission_groups.json", "r") as f:
    groups = json.load(f)

# We need these capabilities
targets = {
    "Access: Apps and Policies Write": "com.cloudflare.api.account",
    "Access: Service Tokens Write": "com.cloudflare.api.account",
    "Cloudflare Tunnel Write": "com.cloudflare.api.account",
    "DNS Write": "com.cloudflare.api.account.zone",
    "Zero Trust Write": "com.cloudflare.api.account",
    "Account Settings Write": "com.cloudflare.api.account",
}

found_ids = {}

for g in groups:
    name = g["name"]
    if name in targets:
        # Check if the scope matches
        if targets[name] in g["scopes"]:
            found_ids[name] = g["id"]
            print(f"Found {name} ({targets[name]}): {g['id']}")

print("\nID List for Script:")
for name, id in found_ids.items():
    print(f'"{id}", # {name}')
