# RustDesk Remote Access Methods - Comprehensive Guide (2025)

## SCENARIO
- **RustDesk GUI is running** on remote Windows machine
- **Ports 21115-21119 are NOT accessible** (firewall blocked)
- **RDP is available** (port 3389)
- **Need to find RustDesk ID or connect directly**

---

## 1. EXTRACT RUSTDESK ID VIA COMMAND LINE

### PowerShell (Windows)
```powershell
# Basic extraction
cd $env:ProgramFiles\RustDesk\
.\rustdesk.exe --get-id

# With output capture
.\rustdesk.exe --get-id | Out-String

# Capture to variable
$rustdesk_id = & "$env:ProgramFiles\RustDesk\rustdesk.exe" --get-id

# Via piping (if output suppressed)
C:\Program Files\RustDesk\rustdesk.exe --get-id | more

# Redirect to file
C:\Program Files\RustDesk\rustdesk.exe --get-id > C:\temp\rustdesk_id.txt
```

### Batch/CMD
```batch
cd "C:\Program Files\RustDesk\"
rustdesk.exe --get-id
```

### Remote Extraction via RDP + PowerShell
```powershell
# Execute remotely via RDP session
$session = New-PSSession -ComputerName [TARGET_IP] -Credential [CRED]
Invoke-Command -Session $session -ScriptBlock {
    cd $env:ProgramFiles\RustDesk\
    .\rustdesk.exe --get-id
}
```

---

## 2. READ RUSTDESK ID FROM CONFIG FILES

### Config File Locations
```
User Profile:    C:\Users\[USERNAME]\AppData\Roaming\RustDesk\config
Service Profile: C:\Windows\ServiceProfiles\LocalService\AppData\Roaming\RustDesk\config
```

### Extract ID from Config (PowerShell)
```powershell
# Read config file
$config_path = "C:\Windows\ServiceProfiles\LocalService\AppData\Roaming\RustDesk\config"
Get-Content $config_path | Select-String "^id"

# Parse ID value
$config = Get-Content $config_path
$id = ($config | Select-String "^id = '(\d+)'" | ForEach-Object {$_.Matches.Groups[1].Value})
Write-Host "RustDesk ID: $id"
```

### Remote Config Access via RDP
```powershell
# Copy config file from remote machine
Copy-Item -Path "\[TARGET_IP]\c$\Windows\ServiceProfiles\LocalService\AppData\Roaming\RustDesk\config" `
          -Destination "C:\temp\rustdesk_config" -Force

# Read locally
Get-Content "C:\temp\rustdesk_config" | Select-String "^id"
```

---

## 3. DIRECT IP CONNECTION (BYPASS RELAY)

### Enable Direct IP Access
1. **On Remote Machine (RustDesk Settings)**:
   - Settings → Security → Enable "Enable direct IP access"
   - Port 21118 must be accessible

2. **On Client Machine**:
   - Instead of entering RustDesk ID, enter **local IP address**
   - Example: `192.168.1.100` instead of `1234567890`
   - Connection is instant but **unencrypted**

### PowerShell to Enable Direct IP (Remote)
```powershell
# Via RDP session
$session = New-PSSession -ComputerName [TARGET_IP] -Credential [CRED]
Invoke-Command -Session $session -ScriptBlock {
    # Edit config file to enable direct IP
    $config_path = "C:\Windows\ServiceProfiles\LocalService\AppData\Roaming\RustDesk\config"
    $config = Get-Content $config_path
    $config = $config -replace "direct-server = 'N'", "direct-server = 'Y'"
    Set-Content -Path $config_path -Value $config
    
    # Restart service
    Restart-Service -Name Rustdesk -Force
}
```

---

## 4. PORT FORWARDING FOR SSH/RDP TUNNELING

### Command Line Syntax
```bash
rustdesk --port-forward [LOCAL_PORT] [REMOTE_HOST] [REMOTE_PORT]
```

### Examples
```bash
# SSH tunneling (forward local 2222 to remote SSH port 22)
rustdesk --port-forward 2222 127.0.0.1 22

# RDP tunneling (forward local 3389 to remote RDP)
rustdesk --port-forward 3389 127.0.0.1 3389

# Custom service (forward local 8080 to remote web server)
rustdesk --port-forward 8080 127.0.0.1 80
```

### GUI Method
1. Establish RustDesk connection
2. Click **lightning bolt icon** in connection popup
3. Configure port forwarding in dialog

### Headless Port Forwarding (No GUI)
```powershell
# Start RustDesk in headless mode with port forwarding
$env:RUSTDESK_ID_SERVER = "your.server"
rustdesk.exe --port-forward 2222 127.0.0.1 22
```

---

## 5. HEADLESS MODE (SERVICE WITHOUT GUI)

### Install RustDesk as Windows Service
```powershell
# Install service
cd $env:ProgramFiles\RustDesk\
.\rustdesk.exe --install-service

# Set permanent password (required for headless)
.\rustdesk.exe --password MySecurePassword123

# Start service
Start-Service -Name Rustdesk

# Verify service is running
Get-Service -Name Rustdesk
```

### Service Configuration File
```
C:\Windows\ServiceProfiles\LocalService\AppData\Roaming\RustDesk\config
```

### PowerShell Script for Headless Setup
```powershell
$ErrorActionPreference = 'silentlycontinue'

# Stop existing service
net stop rustdesk

# Install service
cd $env:ProgramFiles\RustDesk\
.\rustdesk.exe --install-service
Start-Sleep -seconds 5

# Set permanent password
$password = "MySecurePassword123"
.\rustdesk.exe --password $password

# Get ID
$rustdesk_id = & .\rustdesk.exe --get-id

# Start service
net start rustdesk

Write-Host "RustDesk ID: $rustdesk_id"
Write-Host "Password: $password"
```

### Linux Headless Mode
```bash
# Enable headless mode
sudo rustdesk --option allow-linux-headless Y

# Set permanent password
sudo rustdesk --password MySecurePassword123

# Get ID
sudo rustdesk --get-id

# Restart service
sudo systemctl restart rustdesk
```

---

## 6. RELAY SERVER CONFIGURATION

### Default Relay Ports
```
ID Server (hbbs):
  - TCP 21115: NAT type test
  - TCP 21116: ID registration, heartbeat
  - UDP 21116: Heartbeat
  - TCP 21118: Web client support

Relay Server (hbbr):
  - TCP 21117: Relay service
  - TCP 21119: Web client relay (websocket)
```

### Configure Custom Relay Server
```powershell
# Via RustDesk Settings UI
# Settings → Network → ID/Relay Server
# Enter: hostname/IP and key

# Via config file
$config_path = "C:\Users\[USER]\AppData\Roaming\RustDesk\config"
Add-Content -Path $config_path -Value @"
[relay]
port_range = "21114-21119"
"@
```

### Environment Variables (Compile-Time)
```powershell
# Set before building RustDesk from source
$env:RENDEZVOUS_SERVER = "tcp://your.server:21117"
$env:RS_PUB_KEY = "your-public-key-string"
```

### Runtime Configuration
```powershell
# Set before launching RustDesk
$env:RUSTDESK_ID_SERVER = "your.server"
$env:RUSTDESK_RELAY_SERVER = "your.relay.server"
& "$env:ProgramFiles\RustDesk\rustdesk.exe"
```

---

## 7. ALTERNATIVE PORT CONFIGURATIONS

### Configure Custom Port Range
```powershell
# Edit config file
$config_path = "C:\Users\[USER]\AppData\Roaming\RustDesk\config"
$config = Get-Content $config_path
$config += "`n[relay]`nport_range = `"21114-21119`""
Set-Content -Path $config_path -Value $config

# Restart RustDesk
Restart-Service -Name Rustdesk -Force
```

### Docker Port Mapping (Custom Ports)
```bash
# Map custom host ports to RustDesk container ports
docker run -d \
  -p 8006:21116 \
  -p 8006:21116/udp \
  -p 8007:21117 \
  -p 8008:21118 \
  -p 8009:21119 \
  rustdesk/rustdesk-server
```

---

## 8. REMOTE ACCESS VIA RDP (WHEN RUSTDESK PORTS BLOCKED)

### Enable RDP on Remote Machine
```powershell
# Enable RDP
reg add "HKEY_LOCAL_MACHINE\SYSTEM\CurrentControlSet\Control\Terminal Server" `
    /v fDenyTSConnections /t REG_DWORD /d 0 /f

# Allow multiple sessions
REG ADD "HKLM\SOFTWARE\Policies\Microsoft\Windows NT\Terminal Services" `
    /v fSingleSessionPerUser /t REG_DWORD /d 0 /f

# Add user to RDP group
net localgroup "Remote Desktop Users" [USERNAME] /add

# Disable firewall (if needed)
netsh advfirewall set allprofiles state off
```

### Connect via RDP
```bash
# Using xfreerdp
xfreerdp /u:[USERNAME] /p:[PASSWORD] /v:[TARGET_IP]

# Using mstsc (Windows)
mstsc /v:[TARGET_IP]

# Using PowerShell
$cred = Get-Credential
Enter-PSSession -ComputerName [TARGET_IP] -Credential $cred
```

---

## 9. POWERSHELL/WMI REMOTE SERVICE ENUMERATION

### Check RustDesk Service Status
```powershell
# Local machine
Get-Service -Name Rustdesk

# Remote machine
Get-Service -ComputerName [TARGET_IP] -Name Rustdesk -Credential [CRED]

# With detailed info
Get-Service -Name Rustdesk | Select-Object Name, Status, StartType, DisplayName
```

### Enumerate All Services (WMI)
```powershell
# Local
Get-WmiObject Win32_Service | Where-Object {$_.Name -like "*rust*"}

# Remote
Get-WmiO
