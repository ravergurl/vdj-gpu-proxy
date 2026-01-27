# Server GPU Performance Issue

## ✓ SUCCESS: Stems Are Working!

VDJ now shows **stems progress (3%+)** and stems are being separated correctly!

## ❌ PROBLEM: Server Using CPU Instead of GPU

**Measured Performance**:
- Session 1: 16.5 seconds
- Session 2: 11.4 seconds
- Session 3: 11.2 seconds

**Expected Performance**:
- With GPU (CUDA): 1-3 seconds
- With CPU: 10-30 seconds ← **Currently happening**

## Root Cause

Your server at `vdj-gpu-direct.ai-smith.net` is processing stems on **CPU** instead of **GPU**.

## How to Fix

### 1. Check Server GPU Status

SSH to your server and verify GPU is available:

```bash
ssh <your-server>

# Check if GPU is detected
nvidia-smi

# Check CUDA is installed
nvcc --version

# Check PyTorch can see GPU
python -c "import torch; print(f'CUDA available: {torch.cuda.is_available()}')"
```

### 2. Verify Server Configuration

Check the server code is using GPU:

```bash
cd <server-repo-path>

# Check current running process
ps aux | grep python | grep vdj

# Check logs for GPU usage
tail -100 <your-server-log-file>
```

### 3. Update Server Code

Your server needs the latest changes (commit `10a98bd` for binary errors):

```bash
cd <server-repo-path>
git pull origin master

# Restart server
# (method depends on how you're running it - systemd, supervisor, screen, etc.)
```

### 4. Force GPU Usage

If GPU exists but isn't being used, check the htdemucs model loading:

In `server/src/vdj_stems_server/http_streaming.py`, verify the model is loaded to GPU:

```python
# Should see something like:
model = htdemucs.load_model(device='cuda')  # or 'cuda:0'
```

## Expected After Fix

Once GPU is properly configured:
- Stems separation: 1-3 seconds per chunk
- VDJ progress bar: Much faster movement
- Overall: ~10x speedup

## Current Status

✓ Client working correctly (batch dimensions, spectrogram detection)
✓ Binary streaming working
✓ Stems showing in VDJ
❌ Server using CPU not GPU → needs configuration

The hard work is done - just need to enable GPU on your server!
