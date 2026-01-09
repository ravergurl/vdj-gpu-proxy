# Server Update Required - Fix Applied

## What Was Fixed

**Commit:** `a7d2ff7` - Fix server to identify audio input by shape

**Problem:** Server assumed first input was audio, but VDJ sends multiple inputs (spectrograms + audio). Server was validating 4D spectrogram tensor as audio → error.

**Solution:** Server now iterates through all inputs and selects the first 2D tensor `[channels, samples]` as audio input.

## Update Your Remote Server

### Quick Commands

```bash
# SSH to your GPU server
ssh user@your-gpu-server

# Navigate to vdj-gpu-proxy
cd /path/to/vdj-gpu-proxy

# Pull the fix
git pull origin master

# Should show: a7d2ff7 fix: identify audio input by shape...

# Update dependencies (in case)
cd server
source .venv/bin/activate
uv pip install -e .

# Restart server with both ports
pkill -f vdj-stems-server
nohup python -m vdj_stems_server --host 0.0.0.0 --port 50051 --http-streaming-port 8081 > server.log 2>&1 &

# Verify both ports are listening
netstat -tulpn | grep -E '(50051|8081)'

# Expected output:
# tcp  0.0.0.0:50051  ... LISTEN  12345/python
# tcp  0.0.0.0:8081   ... LISTEN  12345/python

# Check server logs for startup
tail -f server.log

# Expected logs:
# INFO:     Uvicorn running on http://0.0.0.0:8081
# gRPC server started on 0.0.0.0:50051
# HTTP streaming server running on 0.0.0.0:8081
```

### Verify Cloudflare Tunnel

```bash
# Check cloudflared is running
ps aux | grep cloudflared

# If not running, deploy it:
bash deploy_cloudflare_tunnel.sh

# Check tunnel logs
tail -f ~/.cloudflared/tunnel.log

# Should show:
# Connection registered
# Registered tunnel connection
```

## Test Locally After Server Update

### Quick Test

```powershell
# Windows - run this after server is updated
cd C:\Users\peopl\work\vdj
.\scripts\test_binary_streaming_e2e.ps1
```

### Expected Output

```
=== Test Results ===

✓ Binary Protocol Used
✓ Correct Endpoint
✓ Connection Success
✓ Audio Input Found          <-- NEW (proves fix works)
✓ Binary Response
✓ Success Status              <-- Should be 0 (was 1 before)
✓ Parsed Outputs

Results: 7 passed, 0 failed

=== TEST PASSED ===
Binary streaming protocol is working correctly!
```

## What Changed in the Code

**File:** `server/src/vdj_stems_server/http_streaming.py`

**Before:**
```python
# Read first input (audio)
input_name, offset = BinaryProtocol.read_string(body, offset)
input_shape, offset = BinaryProtocol.read_shape(body, offset)
# ... use first input as audio
```

**After:**
```python
# Read all inputs and find the audio tensor (2D)
for i in range(num_inputs):
    input_name, offset = BinaryProtocol.read_string(body, offset)
    input_shape, offset = BinaryProtocol.read_shape(body, offset)
    # ...
    if len(input_shape) == 2:  # Audio is 2D: [channels, samples]
        audio_data = input_data_buf
        audio_shape = input_shape
        break
```

## Troubleshooting

### If test still fails with "got 4 dimensions"

Server wasn't updated properly:
```bash
cd /path/to/vdj-gpu-proxy
git log -1
# Should show: a7d2ff7 fix: identify audio input by shape

# If not, force pull:
git fetch origin
git reset --hard origin/master

# Restart server
pkill -f vdj-stems-server
cd server && source .venv/bin/activate
nohup python -m vdj_stems_server --host 0.0.0.0 --port 50051 --http-streaming-port 8081 > server.log 2>&1 &
```

### If test shows 404 errors

Cloudflare tunnel not routing correctly:
```bash
# Check tunnel config
cat ~/.cloudflared/config.yml

# Should have:
# ingress:
#   - hostname: vdj-gpu-direct.ai-smith.net
#     service: http://localhost:8081

# Restart tunnel
pkill cloudflared
bash deploy_cloudflare_tunnel.sh
```

### If server won't start

Check port conflicts:
```bash
# Kill anything on 8081
lsof -ti:8081 | xargs kill -9

# Try starting again
cd /path/to/vdj-gpu-proxy/server
source .venv/bin/activate
python -m vdj_stems_server --host 0.0.0.0 --port 50051 --http-streaming-port 8081
```

## Next Steps

1. Update server (commands above)
2. Run test: `.\scripts\test_binary_streaming_e2e.ps1`
3. If test passes → Binary streaming is fully working! 🎉
4. If test fails → Check troubleshooting section above
