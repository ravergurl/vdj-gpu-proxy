# Deploy Binary Streaming Update

This guide deploys the binary streaming protocol to your remote GPU server.

## What Changed

- **Binary protocol**: Replaces JSON+base64 with efficient binary encoding (~67% bandwidth reduction)
- **HTTP streaming**: FastAPI endpoint on port 8081 streams stems progressively
- **Cloudflare tunnel compatibility**: HTTP works through Cloudflare (gRPC doesn't)

## Deployment Steps

### 1. On Remote GPU Server

```bash
# SSH to your remote GPU server
ssh user@your-gpu-server

# Navigate to the vdj-gpu-proxy directory
cd /path/to/vdj-gpu-proxy  # Adjust to your actual path

# Pull latest code
git pull origin master

# Install/update Python dependencies
cd server
source .venv/bin/activate
uv pip install -e .

# Restart the server with both gRPC and HTTP streaming
pkill -f vdj-stems-server
nohup python -m vdj_stems_server --host 0.0.0.0 --port 50051 --http-streaming-port 8081 > server.log 2>&1 &

# Verify server is running on both ports
sleep 3
netstat -tulpn | grep -E '(50051|8081)'

# View server logs
tail -f server.log
```

Expected output:
```
INFO:     Started server process [PID]
INFO:     Waiting for application startup.
INFO:     Application startup complete.
INFO:     Uvicorn running on http://0.0.0.0:8081 (Press CTRL+C to quit)
gRPC server started on 0.0.0.0:50051
HTTP streaming server running on 0.0.0.0:8081
```

### 2. Update Cloudflare Tunnel Configuration

```bash
# Still on remote GPU server
cd /path/to/vdj-gpu-proxy

# Run the deployment script
bash deploy_cloudflare_tunnel.sh
```

This script will:
- Install cloudflared (if not present)
- Create credentials file
- Configure tunnel to route to port 8081
- Start cloudflared in background
- Log to `~/.cloudflared/tunnel.log`

### 3. Verify Tunnel

```bash
# Check cloudflared is running
ps aux | grep cloudflared

# Monitor tunnel logs
tail -f ~/.cloudflared/tunnel.log
```

Expected log output:
```
INF Starting tunnel tunnelID=831e1b5b-33d5-4ef3-a4c8-b4e4eccda4d8
INF Connection registered connIndex=0 location=XXXX
INF Registered tunnel connection
```

### 4. Test from Windows Client

On your Windows VDJ machine:

```powershell
# Verify registry is configured for HTTPS tunnel
reg query "HKCU\Software\VDJ-GPU-Proxy"
```

Expected output:
```
TunnelUrl    REG_SZ    https://vdj-gpu-direct.ai-smith.net
Enabled      REG_DWORD    0x1
```

### 5. Test in VirtualDJ

1. Start VirtualDJ
2. Load a track
3. Watch DebugView for binary protocol logs:
   - `HTTP: RunInferenceBinary START`
   - `HTTP: Binary request size=...` (should be ~4MB, not 28MB)
   - `HTTP: Got binary response length=...` (should be ~12MB, not 16.5MB)

## Performance Improvements

| Metric | Before (JSON) | After (Binary) | Improvement |
|--------|---------------|----------------|-------------|
| Upload | 28MB | 4.2MB | 85% reduction |
| Download | 16.5MB | ~12MB | 27% reduction |
| Encoding | Base64 | Raw binary | 33% faster |
| Progress | None | Streaming | Real-time |

## Troubleshooting

### Server won't start on port 8081

```bash
# Check if port is already in use
lsof -i :8081

# Kill process using port
kill $(lsof -t -i:8081)
```

### Cloudflared not connecting

```bash
# Check tunnel logs
tail -100 ~/.cloudflared/tunnel.log

# Restart cloudflared
pkill -f cloudflared
bash deploy_cloudflare_tunnel.sh
```

### VDJ shows connection errors

```powershell
# Check Windows client can reach tunnel
curl https://vdj-gpu-direct.ai-smith.net/health

# Should return: {"status": "ok"}
```

### Still seeing JSON/base64 in logs

- DLL was updated and installed locally
- Verify `onnxruntime.dll` in `C:\Program Files\VirtualDJ` is the new version (11MB)
- Check file timestamp matches recent build

## Rollback

If issues occur:

```bash
# On remote server - stop new services
pkill -f vdj-stems-server
pkill -f cloudflared

# Start old gRPC-only server
cd /path/to/vdj-gpu-proxy/server
source .venv/bin/activate
nohup python -m vdj_stems_server --host 0.0.0.0 --port 50051 > server.log 2>&1 &
```

```powershell
# On Windows - switch back to JSON endpoint
# (Edit ort_hooks.cpp to use RunInference instead of RunInferenceBinary, rebuild DLL)
```

## Files Modified

- `server/src/vdj_stems_server/http_streaming.py` - New binary streaming endpoint
- `server/src/vdj_stems_server/main.py` - Run both gRPC and HTTP servers
- `proxy-dll/src/http_client.cpp` - Binary protocol client implementation
- `proxy-dll/src/ort_hooks.cpp` - Switch to RunInferenceBinary()
- `deploy_cloudflare_tunnel.sh` - Automated tunnel deployment
- `cloudflared-remote-config.yml` - Tunnel configuration for port 8081
