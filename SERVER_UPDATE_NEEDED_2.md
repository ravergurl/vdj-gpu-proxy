# Server Update Required - Binary Error Format Fix

## Problem Found

VDJ makes multiple inference calls:
1. **First call**: 2 inputs `[2,531456]` + `[1,4,2048,519]` - requests stems (SUCCESS)
2. **Second call**: 1 input `[1,4,3072,256]` - different processing (FAILS)

The second call fails because:
- VDJ sends a 4D spectrogram tensor instead of 2D audio
- Server error: "No 2D audio input found among 1 inputs"
- Server returned error as PLAIN TEXT (HTTP 400)
- Client tried to parse as BINARY PROTOCOL → crash
- Fallback to local inference → stems show 0%

## Fix Applied

**Commit**: `10a98bd`
**File**: `server/src/vdj_stems_server/http_streaming.py`

Server now returns errors in binary protocol format:
```
session_id (uint32): 0
status (uint32): 1 (error)
error_message (string): error details
```

## Update Steps

### If Server is Remote (vdj-gpu-direct.ai-smith.net):

```bash
# SSH to server
ssh <server-hostname>

# Navigate to repo
cd ~/vdj-stems-server  # or wherever the repo is

# Pull latest changes
git pull origin master

# Restart server (method depends on your setup)
# If using systemd:
sudo systemctl restart vdj-stems-server

# If running manually:
pkill -f "python.*http_streaming"
python -m vdj_stems_server.http_streaming &
```

### If Server is Local:

```bash
cd C:\Users\peopl\work\vdj\server
# Restart your local server process
```

## What This Fixes

- Client will now properly parse server errors
- Errors will be logged clearly instead of causing "String read would exceed buffer"
- Client can decide whether to fallback to local or retry

## What's Still Not Working

Even with this fix, stems still show 0% because:
1. First call (stems separation) SUCCEEDS but VDJ doesn't use the data
2. Second call (spectrogram processing) FAILS and falls back to local

**Root issue**: VDJ might need BOTH calls to succeed, or might need 4 outputs instead of 2.

## Next Steps

1. Update server with this fix
2. Test again to see clearer error messages
3. Investigate why VDJ doesn't use the successfully returned stems
4. Consider adding support for 4D spectrogram inputs
