# VDJ-GPU-Proxy Remote Server Deployment

## Overview
Deploy the Python gRPC server on a remote GPU machine to offload VirtualDJ stems processing.

**IMPORTANT:** Cloudflare Tunnel does NOT support gRPC over public hostnames. You must use direct IP:port access or VPN.

## Remote Server Setup

### Prerequisites
- Linux machine with NVIDIA GPU (8GB+ VRAM recommended)
- CUDA 11.8+ and cuDNN installed
- Python 3.10+
- Open firewall port 50051 (or your chosen port)

### Installation Steps

```bash
# 1. Clone repository
git clone https://github.com/ravergurl/vdj-gpu-proxy.git
cd vdj-gpu-proxy

# 2. Install server dependencies (using uv - recommended)
cd server
uv venv && source .venv/bin/activate
uv pip install -e .

# Or using pip
python3 -m venv .venv && source .venv/bin/activate
pip install -e .

# 3. Generate proto files
cd ..
python scripts/generate_proto.py

# 4. Start the server
cd server
vdj-stems-server --host 0.0.0.0 --port 50051

# Or run in background with nohup
nohup vdj-stems-server --host 0.0.0.0 --port 50051 > server.log 2>&1 &
```

### Firewall Configuration

```bash
# Ubuntu/Debian
sudo ufw allow 50051/tcp
sudo ufw reload

# CentOS/RHEL
sudo firewall-cmd --permanent --add-port=50051/tcp
sudo firewall-cmd --reload
```

### Test Server Health

```bash
vdj-stems-health --host 127.0.0.1 --port 50051
```

## Windows Client Configuration

### Option 1: Direct IP Connection (Recommended)

On your Windows VirtualDJ machine:

```powershell
# Configure proxy to connect to remote server
$remoteIP = "YOUR_REMOTE_SERVER_IP"  # e.g., "192.168.1.100"
$remotePort = 50051

Set-ItemProperty -Path "HKCU:\Software\VDJ-GPU-Proxy" -Name "TunnelUrl" -Value ""
Set-ItemProperty -Path "HKCU:\Software\VDJ-GPU-Proxy" -Name "ServerAddress" -Value $remoteIP
Set-ItemProperty -Path "HKCU:\Software\VDJ-GPU-Proxy" -Name "ServerPort" -Value $remotePort
Set-ItemProperty -Path "HKCU:\Software\VDJ-GPU-Proxy" -Name "Enabled" -Value 1
```

### Option 2: SSH Tunnel (Alternative)

If you cannot open firewall ports, use SSH tunnel:

```powershell
# On Windows, install OpenSSH client first, then:
ssh -L 50051:localhost:50051 user@remote-server

# Then configure proxy for localhost
Set-ItemProperty -Path "HKCU:\Software\VDJ-GPU-Proxy" -Name "ServerAddress" -Value "127.0.0.1"
Set-ItemProperty -Path "HKCU:\Software\VDJ-GPU-Proxy" -Name "ServerPort" -Value 50051
```

## Cloudflare Tunnel Information (NOT FOR GRPC)

**Note:** Cloudflare Tunnel was set up but does NOT support gRPC over public hostnames. These are provided for reference only.

### Tunnel Credentials

**vdj-remote Tunnel Token:**
```
eyJhIjoiNGMyOTMyYmMzMzgxYmUzOGQ1MjY2MjQxYjE2YmUwOTIiLCJ0IjoiOTBkZDY5YWItNGE0ZS00MGRjLTllOTMtMDhhMzMyODY4NjQ1IiwicyI6IjVRc1Zxc1JUYXpsRWhDTDhiTzNKWVorNHNJdGJtbElvaGtNVHlNdnlrT1k9In0=
```

**Tunnel Details:**
- Tunnel ID: `90dd69ab-4a4e-40dc-9e93-08a332868645`
- Tunnel Name: `vdj-remote`
- Account: `4c2932bc3381be38d5266241b16be092`

### To Deploy (if you want to try despite gRPC limitations):

```bash
# 1. Install cloudflared
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared
chmod +x /usr/local/bin/cloudflared

# 2. Create credentials file
mkdir -p ~/.cloudflared
cat > ~/.cloudflared/90dd69ab-4a4e-40dc-9e93-08a332868645.json <<EOF
{
  "AccountTag": "4c2932bc3381be38d5266241b16be092",
  "TunnelID": "90dd69ab-4a4e-40dc-9e93-08a332868645",
  "TunnelName": "vdj-remote",
  "TunnelSecret": "5QsVqsRTazlEhCL8bO3JYZ+4sItbmlIohkMTyMvykOY="
}
EOF

# 3. Create config file
cat > ~/.cloudflared/config.yml <<EOF
tunnel: 90dd69ab-4a4e-40dc-9e93-08a332868645
credentials-file: /root/.cloudflared/90dd69ab-4a4e-40dc-9e93-08a332868645.json

warp-routing:
  enabled: true

ingress:
  - service: http_status:404
EOF

# 4. Run tunnel
cloudflared tunnel --config ~/.cloudflared/config.yml run
```

**DNS Hostname:** `vdj-remote.ai-smith.net`

**Again:** This will NOT work for gRPC. Use direct IP connection instead.

## Verification

### Test Remote Connection

From Windows:
```powershell
cd server
.venv\Scripts\python.exe -m vdj_stems_server.cli --host YOUR_REMOTE_IP --port 50051
```

Expected output:
```
Checking server at YOUR_REMOTE_IP:50051...
HEALTHY
  Version: 1.0.0
  Model: htdemucs
  GPU Memory: XXXX MB
  Ready: True
```

### Monitor Server

```bash
# Check server logs
tail -f server/server.log

# Monitor GPU usage
nvidia-smi -l 1

# Check connections
netstat -tulpn | grep 50051
```

## Troubleshooting

### Connection Refused
- Check firewall: `sudo ufw status`
- Verify server is listening: `netstat -tulpn | grep 50051`
- Test from server itself: `curl -v http://localhost:50051`

### Performance Issues
- Check GPU utilization: `nvidia-smi`
- Monitor network latency: `ping YOUR_REMOTE_IP`
- Check server logs for errors

### VDJ Proxy Not Connecting
- Verify registry settings: `Get-ItemProperty -Path "HKCU:\Software\VDJ-GPU-Proxy"`
- Check proxy logs: `C:\Users\[USER]\AppData\Local\VDJ-GPU-Proxy\`
- Verify DLL is installed: `C:\Users\[USER]\AppData\Local\VirtualDJ\Drivers\ml1151.dll`

## Production Deployment

For production use, consider:

1. **Systemd Service** (Linux):
```bash
sudo tee /etc/systemd/system/vdj-stems.service <<EOF
[Unit]
Description=VDJ Stems Server
After=network.target

[Service]
Type=simple
User=gpu-user
WorkingDirectory=/opt/vdj-gpu-proxy/server
ExecStart=/opt/vdj-gpu-proxy/server/.venv/bin/vdj-stems-server --host 0.0.0.0 --port 50051
Restart=always

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl enable vdj-stems
sudo systemctl start vdj-stems
```

2. **VPN/Wireguard** for secure remote access (better than open ports)

3. **Monitoring** with Prometheus/Grafana

4. **Load balancing** for multiple GPU servers
