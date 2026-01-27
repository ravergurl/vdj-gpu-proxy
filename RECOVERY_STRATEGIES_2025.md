# Server Recovery Strategies - Comprehensive Analysis

## Executive Summary

After extensive research, we have identified **3 viable attack vectors** and **2 theoretical vectors** for recovering access to `meltat0`.

---

## Current State

### Tunnel Status: HEALTHY
- **Tunnel ID**: `926eac5e-2642-4a16-9edc-c06b6c705ab8`
- **Origin IP**: `68.197.247.79`
- **Active Connections**: 4 (ord10, ewr12, ord02, ord11)
- **Client Version**: cloudflared 2024.9.1
- **WARP Routing**: ENABLED

### Configured Services (from API)
| Hostname | Service | Port | Status |
|----------|---------|------|--------|
| rdp.ai-smith.net | tcp://localhost:3389 | 3389 | ACTIVE (NLA required) |
| http.ai-smith.net | tcp://localhost:80 | 80 | NOT RUNNING |
| https.ai-smith.net | tcp://localhost:443 | 443 | NOT RUNNING |
| vnc.ai-smith.net | tcp://localhost:5900 | 5900 | NOT RUNNING |
| iis.ai-smith.net | tcp://localhost:8000 | 8000 | NOT RUNNING |
| api.ai-smith.net | tcp://localhost:5000 | 5000 | NOT RUNNING |
| node.ai-smith.net | tcp://localhost:3000 | 3000 | NOT RUNNING |
| db.ai-smith.net | tcp://localhost:1433 | 1433 | NOT RUNNING |
| mysql.ai-smith.net | tcp://localhost:3306 | 3306 | NOT RUNNING |
| postgres.ai-smith.net | tcp://localhost:5432 | 5432 | NOT RUNNING |

### Known Credentials
- **Usernames**: `melody`, `kuro`
- **Domain**: `meltat0`
- **PINs**: `1121`, `0114`, `0441`
- **Password**: UNKNOWN (that's our problem)

---

## VECTOR 1: Windows Hello PIN Password Extraction (HIGHEST PROBABILITY)

### Theory
When Windows Hello PIN is configured on systems WITHOUT a TPM, the actual Windows password is stored encrypted on disk. The PIN is used to derive a key that decrypts it.

### Technical Details
- Password stored in: `HKLM\...\NgcPin\Credentials\<SID>\EncryptedPassword`
- OR in Windows Vault: `%windir%\System32\config\systemprofile\AppData\Local\Microsoft\Vault\`
- Decryption chain: `PIN -> PBKDF2-SHA256 -> RSA Private Key -> DPAPI blob -> Plaintext Password`

### Required Files (from remote server)
```
C:\Windows\ServiceProfiles\LocalService\AppData\Local\Microsoft\Ngc\
C:\Windows\ServiceProfiles\LocalService\AppData\Roaming\Microsoft\Crypto\Keys\
C:\Windows\System32\config\SYSTEM
C:\Windows\System32\config\SECURITY
C:\Windows\System32\config\SOFTWARE
```

### Tools
1. **dpapilab-ng** (https://github.com/tijldeneut/dpapilab-ng)
   - `ngccryptokeysdec.py` - Decrypt Crypto\Keys with PIN
   - `ngcvaultdec.py` - Decrypt NGC vault files
   - `_ngc_full_auto.py` - Automated full decryption

2. **WINHELLO2hashcat** (https://github.com/Banaanhangwagen/WINHELLO2hashcat)
   - Extract hash for offline PIN cracking if needed

### Prerequisites
- **NO TPM on target** (if TPM is present, this won't work)
- Access to the file system (we don't currently have this)

### How to Get File Access
This is the chicken-and-egg problem. Options:
1. Run a rogue replica that intercepts file requests (complex)
2. If any other service starts running, use that for file access
3. Physical access (not available)

### Viability: HIGH if no TPM, requires file system access

---

## VECTOR 2: Cloudflare Tunnel Rogue Replica (AiTM)

### Theory (from y4nush research)
With the tunnel token, we can run a "rogue replica" that intercepts some traffic randomly. This is designed for high availability but can be abused.

### What We Can Do
1. **Run our own cloudflared with the stolen token**
2. **Intercept random requests** (Cloudflare routes by geography)
3. **Capture session tokens** from authenticated users
4. **Serve malicious content** when requests hit our replica

### Limitation for Our Scenario
- This is for INBOUND traffic interception
- We need OUTBOUND access to the server
- **Does NOT help us authenticate to RDP**
- Would only help if there was an authenticated HTTP app we could hijack

### Potential Use
If `http.ai-smith.net` was serving an admin panel and someone was logged in, we could:
1. Intercept their session
2. Use their session to access admin functions
3. Potentially reset password from admin panel

### Current Reality
No HTTP services are running on the server, so this vector is NOT useful now.

### Viability: LOW (no HTTP services running)

---

## VECTOR 3: Tunnel Configuration Modification

### Theory
We have API access to modify the tunnel configuration. Can we add a service that gives us shell access?

### Current Configuration API Access
```bash
curl -s "https://api.cloudflare.com/client/v4/accounts/4c2932bc3381be38d5266241b16be092/cfd_tunnel/926eac5e-2642-4a16-9edc-c06b6c705ab8/configurations" \
  -H "Authorization: Bearer ySIb_2uMzHQDvnK5MulcCvOiRKsC6k0pH188bG8Y"
```

### What We Could Try
1. **Add SSH service** (won't work - SSH isn't running on server)
2. **Add PowerShell Remoting** (port 5985/5986) - also not running
3. **Modify existing service to point elsewhere** - doesn't help

### Key Insight
Modifying the tunnel configuration only changes which LOCAL ports the cloudflared process connects to. If those services aren't running on the Windows server, it doesn't matter.

**The tunnel is a passthrough - it can't start services on the remote machine.**

### Viability: LOW (can't start services remotely)

---

## VECTOR 4: Windows Hello Bypass via RDP Protocol

### Research Findings (DEF CON 32)
From "Abusing Windows Hello Without a Severed Hand" by Ceri Coburn & Dirk-jan Mollema:
- Windows Hello can be abused for Entra ID / Azure AD scenarios
- PRT (Primary Refresh Token) theft is possible
- **Does NOT apply to local account + local RDP scenario**

### CVE Research 2024
- No new NLA bypass CVEs discovered in 2024-2025
- CVE-2019-9510 (screen lock bypass) only works on existing sessions
- BlueKeep (CVE-2019-0708) patched and requires NLA disabled

### Viability: VERY LOW

---

## VECTOR 5: Microsoft Account Recovery

### Theory
If the Windows account is linked to a Microsoft Account, password can be reset online.

### Check Required
Ask user:
1. Is `melody` or `kuro` linked to a Microsoft Account?
2. Do you have access to the recovery email/phone?

### Process
1. Go to https://account.live.com/password/reset
2. Enter the Microsoft Account email
3. Verify via recovery method
4. Set new password
5. New password works for RDP

### Viability: MEDIUM-HIGH (if MS account linked)

---

## RECOMMENDED ACTION PLAN

### Phase 1: Information Gathering (Immediate)
Ask user:
- [ ] Is your Windows account linked to a Microsoft Account?
- [ ] Is the device Azure AD / Entra ID joined?
- [ ] Is Windows LAPS configured?
- [ ] Was Intune ever set up?
- [ ] Does the machine have a TPM? (affects PIN extraction viability)
- [ ] Are there any other admin accounts?

### Phase 2: Try Microsoft Recovery (If Applicable)
If MS Account linked:
1. https://account.live.com/password/reset
2. Reset password
3. Use new password for RDP

### Phase 3: Attempt to Enable Additional Services
Since WARP routing is enabled, investigate:
- Can we route to internal network services?
- Is there another machine on the same network?

### Phase 4: Physical Access Contingency
If someone can get physical access for 5 minutes:
1. Boot from Linux USB
2. Mount Windows partition
3. Extract NGC files + registry hives
4. Use dpapilab-ng with known PINs to recover password
5. Alternatively: Use chntpw to reset password directly

---

## Tools to Prepare

### For PIN Password Extraction (if we get file access)
```bash
# Clone dpapilab-ng
git clone https://github.com/tijldeneut/dpapilab-ng
cd dpapilab-ng
pip install -r requirements.txt

# Usage (with extracted files)
python _ngc_full_auto.py --windows /path/to/extracted/windows --pin 1121
```

### For Hashcat PIN Cracking (if PIN unknown)
```bash
# Clone WINHELLO2hashcat
git clone https://github.com/Banaanhangwagen/WINHELLO2hashcat
# Extract hash
python winhello2hashcat.py --ngc <NGC_folder> --cryptokeys <CryptoKeys> \
    --masterkey <MasterKey_folder> --system <SYSTEM> --security <SECURITY>
# Crack with hashcat
hashcat -m 28100 hash.txt -a 3 ?d?d?d?d  # 4-digit PIN
```

### For Rogue Replica (if HTTP service starts)
```bash
# Clone PoC
git clone https://github.com/Y4nush/cloudflared_aitm_poc
# Run with our token
python aitm_server.py --token "eyJhIjoiNGMyOTMyYmMzMzgxYmUzOGQ1MjY2MjQxYjE2YmUwOTIiLCJ0IjoiOTI2ZWFjNWUtMjY0Mi00YTE2LTllZGMtYzA2YjZjNzA1YWI4IiwicyI6Ik1USTJNR0l6TURrdFpHTTBOaTAwTWpBMUxXRmhNV0V0T1dFNU5tVXpPRFU0ZDUwIn0="
```

---

## Critical Question for User

**The most important thing to determine is: Is the Windows account a local account or a Microsoft Account?**

If Microsoft Account: We can likely recover via https://account.live.com/password/reset
If Local Account: We need file system access or physical access to extract/reset password

---

## References

1. dpapilab-ng: https://github.com/tijldeneut/dpapilab-ng
2. DPAPI In-Depth: https://www.insecurity.be/blog/2020/12/24/dpapi-in-depth-with-tooling-standalone-dpapi/
3. WINHELLO2hashcat: https://github.com/Banaanhangwagen/WINHELLO2hashcat
4. Cloudflared Replica Exploitation: https://y4nush.com/posts/when-replicas-go-rogue-a-deep-dive-into-cloudflared-replicas-exploitation-scenarios/
5. Windows Hello DEF CON 32: https://dirkjanm.io/assets/raw/Abusing%20Windows%20Hello%20Without%20a%20Severed%20Hand_v3.pdf
6. Elcomsoft Windows Hello: https://blog.elcomsoft.com/2022/08/windows-hello-no-tpm-no-security/
