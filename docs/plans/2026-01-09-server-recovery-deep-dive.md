# Server Recovery Deep Dive: Operation Sisyphus

## Objective
Regain administrative access to Windows Server `meltat0` (Cloudflare Tunnel: `home`).
**Constraint:** No password (only PIN), NLA enabled, no physical access.

## Strategic Framework (Hermeneutic Circle)
We interpret the "locked door" (NLA) not just as a barrier, but as a system component with dependencies.
- **Dependency 1:** Network Transport (Cloudflare Tunnel). We own this.
- **Dependency 2:** Authentication Provider (Windows LSA). We have partial credentials (PIN).
- **Dependency 3:** Protocol (RDP). It has legacy modes and potential bypasses.

## Attack Vectors

### Vector A: Tunnel Configuration Exploitation (The "Inside Man")
**Theory:** The `cloudflared` daemon runs as System/Admin. If we can instruct it to do something other than "proxy localhost:3389", we win.
1. **File URI Scheme:** Does `cloudflared` ingress support `file://` or `http://localhost:admin_port`?
2. **Management Interface:** Does the remote `cloudflared` expose a metrics/debug port (localhost:20241)? Can we route *to* that port via the tunnel?
3. **Rogue Replica:** Run a local `cloudflared` with the SAME token. Does it receive config updates? Can we "poison" the config?

### Vector B: RDP Protocol Attacks (The "Lock Pick")
**Theory:** NLA is a negotiation. We can influence it.
1. **Restricted Admin Mode:** Attempt connection with `/restrictedAdmin`.
2. **RDP Downgrade:** Force client to request "Standard RDP Security". If server allows it (even if NLA is "on"), it might fallback.
3. **CredSSP Injection:** Use Cloudflare Access to wrap the RDP connection. Does Cloudflare have a mechanism to "sign" the RDP connection (Short-lived Certs) that bypasses password?

### Vector C: Side-Channel Authentication (The "Back Window")
**Theory:** Services other than RDP might accept the PIN or weaker auth.
1. **SMB / IPC$:** Use `smbprotocol` to hit the mapped SMB port. Try null session, guest, or known usernames.
2. **RPC Enumeration:** If SMB connects, use RPC to list users/groups.
3. **WinRM / PowerShell Direct:** If we map `5985`, can we use `Evil-WinRM`?

### Vector D: Network Lateral Movement (The "Ventilation Shaft")
**Theory:** The server is on a LAN (`192.168.1.0/24`). Other devices might be accessible via WARP.
1. **WARP Fix:** Fix the local WARP client connectivity issues.
2. **Scan LAN:** Once WARP works, scan `192.168.1.x` for OTHER vulnerable machines.
3. **Pivot:** Compromise a secondary machine (printer, IoT, old PC) to launch attacks against `meltat0` from the inside.

## Execution Plan

### Phase 1: Intelligence Gathering (Subagents)
- **Agent 1 (Tunnel Expert):** Investigate `cloudflared` local ingress capabilities (file://, metrics ports).
- **Agent 2 (RDP Specialist):** Research "Bypassing NLA with PIN" or "Cloudflare Access RDP Certificates without AD".
- **Agent 3 (SMB/RPC):** Deep dive into `smbprotocol` for "Pass-the-PIN" or Hash extraction.

### Phase 2: Infrastructure Stabilization
- **Task:** Fix WARP client on `TogetherWeRave`.
- **Task:** Verify SMB Tunnel stability (`smb.ai-smith.net`).

### Phase 3: Active Exploitation
- **Action:** Attempt `file://` ingress rule injection.
- **Action:** Run `brute_smb.py` with refined wordlist.
- **Action:** Attempt RDP with "Restricted Admin" flag.

---
**Status:** Planning...
