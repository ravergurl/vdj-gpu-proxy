# RustDesk Remote Access - Complete Reference Index

**Date**: January 8, 2025  
**Scenario**: RustDesk GUI running, ports 21115-21119 blocked, RDP available  
**Versions Tested**: RustDesk 1.4.1+, Windows 10/11, Windows Server 2019/2022, Ubuntu 20.04+

---

## 📋 Documentation Files

### 1. **RUSTDESK_REMOTE_ACCESS_GUIDE.md** (339 lines)
Comprehensive guide with detailed PowerShell scripts and step-by-step instructions for all access methods.

**Sections**:
- Extract RustDesk ID via command line
- Read ID from config files
- Direct IP connection (bypass relay)
- Port forwarding for SSH/RDP tunneling
- Headless mode (service without GUI)
- Relay server configuration
- Alternative port configurations
- Remote access via RDP (fallback)
- PowerShell/WMI remote service enumeration
- Environment variables
- Terminal/SSH access (v1.4.1+)
- Firewall bypass strategies
- Registry keys (Windows)
- Installation & service management
- Critical ports reference
- Troubleshooting
- Quick reference commands
- Summary table: Access methods by scenario

### 2. **RUSTDESK_METHODS_SUMMARY.txt** (228 lines)
Quick reference guide with all commands and methods in condensed format.

**Sections**:
- Extract RustDesk ID - command line methods
- Read ID from config files
- Direct IP connection (bypass relay)
- Port forwarding for SSH/RDP tunneling
- Headless mode (service without GUI)
- Relay server configuration
- Alternative port configurations
- Remote access via RDP (fallback)
- PowerShell/WMI remote service enumeration
- Environment variables
- Terminal/SSH access (v1.4.1+)
- Firewall bypass strategies
- Registry keys (Windows)
- Installation & service management
- Critical ports reference
- Quick reference commands
- Troubleshooting
- Access methods comparison table

---

## 🎯 Quick Start by Scenario

### Scenario 1: Extract RustDesk ID Remotely
**Use**: RUSTDESK_REMOTE_ACCESS_GUIDE.md → Section 1 or 2

```powershell
# Fastest method
cd $env:ProgramFiles\RustDesk\
.\rustdesk.exe --get-id | Out-String
```

### Scenario 2: Connect via Direct IP (Same LAN)
**Use**: RUSTDESK_REMOTE_ACCESS_GUIDE.md → Section 3

```powershell
# Enable on remote machine
Settings → Security → "Enable direct IP access"

# On client, use local IP instead of ID
# Example: 192.168.1.100
```

### Scenario 3: Ports Blocked - Use RDP Fallback
**Use**: RUSTDESK_REMOTE_ACCESS_GUIDE.md → Section 8

```powershell
# Enable RDP on remote
reg add "HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\Terminal Server" `
    /v fDenyTSConnections /t REG_DWORD /d 0 /f

# Connect
mstsc /v:[TARGET_IP]
```

### Scenario 4: SSH Tunneling Through RustDesk
**Use**: RUSTDESK_REMOTE_ACCESS_GUIDE.md → Section 4

```bash
rustdesk --port-forward 2222 127.0.0.1 22
```

### Scenario 5: Headless Remote Access (No GUI)
**Use**: RUSTDESK_REMOTE_ACCESS_GUIDE.md → Section 5

```powershell
rustdesk.exe --install-service
rustdesk.exe --password MyPassword123
Start-Service -Name Rustdesk
```

### Scenario 6: Enumerate Remote Services
**Use**: RUSTDESK_REMOTE_ACCESS_GUIDE.md → Section 9

```powershell
Get-Service -ComputerName [IP] -Name Rustdesk -Credential [CRED]
Get-WmiObject -ComputerName [IP] -Class Win32_Service | Where-Object {$_.Name -like "*rust*"}
```

---

## 🔧 Command Reference by Category

### ID Extraction
| Command | Purpose | File |
|---------|---------|------|
| `rustdesk.exe --get-id` | Get RustDesk ID | Guide §1 |
| `rustdesk.exe --get-id \| Out-String` | Get ID with output capture | Guide §1 |
| Read config file | Extract ID from config | Guide §2 |
| Remote PowerShell | Get ID via RDP session | Guide §1 |

### Service Management
| Command | Purpose | File |
|---------|---------|------|
| `rustdesk.exe --install-service` | Install as Windows service | Guide §5 |
| `rustdesk.exe --password [pwd]` | Set permanent password | Guide §5 |
| `Get-Service -Name Rustdesk` | Check service status | Guide §9 |
| `Restart-Service -Name Rustdesk` | Restart service | Guide §5 |

### Port Forwarding
| Command | Purpose | File |
|---------|---------|------|
| `rustdesk --port-forward 2222 127.0.0.1 22` | SSH tunneling | Guide §4 |
| `rustdesk --port-forward 3389 127.0.0.1 3389` | RDP tunneling | Guide §4 |
| Lightning bolt icon | GUI port forwarding | Guide §4 |

### Firewall/Network
| Command | Purpose | File |
|---------|---------|------|
| Enable direct IP | Bypass relay on LAN | Guide §3 |
| Force relay | Disable P2P connections | Guide §12 |
| Disable UDP | Force relay fallback | Guide §12 |
| HTTP/HTTPS proxy | Bypass firewall | Guide §12 |

### RDP (Fallback)
| Command | Purpose | File |
|---------|---------|------|
| `reg add ... fDenyTSConnections /d 0` | Enable RDP | Guide §8 |
| `mstsc /v:[IP]` | Connect via RDP | Guide §8 |
| `xfreerdp /u:[USER] /p:[PASS] /v:[IP]` | RDP via xfreerdp | Guide §8 |

---

## 📊 Port Reference

| Port | Protocol | Service | Purpose | Blockable |
|------|----------|---------|---------|-----------|
| 21114 | TCP | hbbs | HTTP (Pro only) | Yes |
| 21115 | TCP | hbbs | NAT type test | Yes |
| 21116 | TCP/UDP | hbbs | ID registration, heartbeat | Yes |
| 21117 | TCP | hbbr | Relay service | Yes |
| 21118 | TCP | hbbs | Web client support | Yes |
| 21119 | TCP | hbbr | Web client relay | Yes |
| 3389 | TCP | RDP | Remote Desktop Protocol | Sometimes |

---

## 🔐 Configuration File Locations

### Windows
```
User Profile:    C:\Users\[USERNAME]\AppData\Roaming\RustDesk\config
Service Profile: C:\Windows\ServiceProfiles\LocalService\AppData\Roaming\RustDesk\config
```

### Linux
```
User Config:     ~/.config/rustdesk/
System Config:   /etc/rustdesk/
```

---

## 🌐 Environment Variables

| Variable | Purpose | Scope |
|----------|---------|-------|
| `RUSTDESK_ID_SERVER` | Custom ID server | Runtime |
| `RUSTDESK_RELAY_SERVER` | Custom relay server | Runtime |
| `IS_TERMINAL_ADMIN` | Terminal admin mode (v1.4.1+) | Runtime |
| `RENDEZVOUS_SERVER` | Rendezvous server | Compile-time |
| `RS_PUB_KEY` | Public key | Compile-time |

---

## 🚀 Access Methods Ranked by Reliability

### When Ports 21115-21119 Are Blocked

1. **RDP (Port 3389)** - Most reliable fallback
   - File: Guide §8
   - Pros: Standard Windows protocol, usually available
   - Cons: Requires RDP enabled on remote

2. **Direct IP Connection** - Fast on LAN
   - File: Guide §3
   - Pros: Instant, no relay needed
   - Cons: Unencrypted, LAN only

3. **Port Forwarding** - Flexible tunneling
   - File: Guide §4
   - Pros: Can tunnel SSH/RDP/custom services
   - Cons: Requires active RustDesk connection

4. **Relay Server** - Always works
   - File: Guide §6
   - Pros: Works across networks
   - Cons: Slower, requires relay server

5. **Headless Service** - Background access
   - File: Guide §5
   - Pros: No GUI needed, persistent
   - Cons: Requires initial setup

6. **Terminal Access** - CLI only (v1.4.1+)
   - File: Guide §11
   - Pros: Lightweight, no display needed
   - Cons: CLI only, limited functionality

---

## 🔍 Troubleshooting Guide

### Problem: RustDesk ID Not Showing
**Solution**: Guide §16 → Troubleshooting
```powershell
Start-Service -Name Rustdesk
Start-Sleep -seconds 5
cd $env:ProgramFiles\RustDesk\
.\rustdesk.exe --get-id
```

### Problem: Connection Fails with Ports Blocked
**Solution**: Guide §12 → Firewall Bypass Strategies
1. Enable direct IP (Guide §3)
2. Force relay (Guide §12)
3. Use RDP fallback (Guide §8)

### Problem: Service Won't Start
**Solution**: Guide §16 → Troubleshooting
```powershell
Get-Service -Name Rustdesk
Restart-Service -Name Rustdesk -Force
rustdesk.exe --uninstall-service
rustdesk.exe --install-service
```

### Problem: Config File Issues
**Solution**: Guide §16 → Troubleshooting
```powershell
Remove-Item -Path "C:\Windows\ServiceProfiles\LocalService\AppData\Roaming\RustDesk\config" -Force
Restart-Service -Name Rustdesk -Force
```

---

## 📚 Related Documentation

- **REMOTE_DEPLOYMENT.md** - Deployment strategies
- **README.md** - Project overview
- Official RustDesk Docs: https://rustdesk.com/docs/

---

## 🎓 Learning Path

### Beginner
1. Read: RUSTDESK_METHODS_SUMMARY.txt (quick overview)
2. Try: Extract ID 
