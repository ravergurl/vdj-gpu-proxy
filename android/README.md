# VDJ Stems Server for Android (Termux)

Run STEM separation on your Pixel 8 Pro via USB connection.

## Prerequisites

- Pixel 8 Pro (or other Android with ARM64)
- Termux installed from F-Droid (NOT Play Store - it's outdated)
- USB debugging enabled
- ADB installed on Windows

## Setup (One-time)

### 1. Install Termux

Download from F-Droid: https://f-droid.org/en/packages/com.termux/

**Important**: The Play Store version is outdated and won't work.

### 2. Transfer Setup Script

```powershell
# On Windows
adb push android/setup_termux.sh /sdcard/
adb push android/termux_server.py /sdcard/
```

### 3. Run Setup in Termux

Open Termux app on phone and run:

```bash
# Copy files from sdcard to Termux home
cp /sdcard/setup_termux.sh ~/
cp /sdcard/termux_server.py ~/vdj-stems/
chmod +x ~/setup_termux.sh

# Run setup (takes 10-15 minutes)
~/setup_termux.sh
```

## Usage

### On Phone (Termux)

```bash
cd ~/vdj-stems
python termux_server.py
```

First run will download the Demucs model (~150MB).

### On Windows

```powershell
# Forward port from phone to localhost
adb forward tcp:8081 tcp:8081

# Verify connection
curl http://127.0.0.1:8081/health
# Should return: {"status":"ok"}
```

### Configure VDJ Proxy

Set registry values:
```powershell
# Point to phone via ADB forwarding
reg add "HKCU\Software\VDJ-GPU-Proxy" /v ServerAddress /t REG_SZ /d "127.0.0.1" /f
reg add "HKCU\Software\VDJ-GPU-Proxy" /v ServerPort /t REG_DWORD /d 8081 /f
reg add "HKCU\Software\VDJ-GPU-Proxy" /v Enabled /t REG_DWORD /d 1 /f
```

## Performance Expectations

| Device | Expected RTF | Notes |
|--------|--------------|-------|
| RTX 3080 | 0.8-1.2x | Baseline GPU |
| Pixel 8 Pro (CPU) | ~0.05-0.1x | 10-20x slower |

The phone will be significantly slower than a desktop GPU, but may be usable for:
- Offline preparation of stems
- Backup when GPU server unavailable
- Testing/development

## Troubleshooting

### "Permission denied" on Termux
```bash
termux-setup-storage  # Grant storage access
```

### ADB forward not working
```bash
# Check device connected
adb devices

# Kill and restart ADB
adb kill-server
adb start-server
adb forward tcp:8081 tcp:8081
```

### Out of memory
- Close other apps on phone
- Try shorter audio clips
- Phone has 12GB RAM but shared with system

### Model download fails
```bash
# Download manually
python -c "from demucs import pretrained; pretrained.get_model('htdemucs')"
```

## Advanced: ONNX Runtime (Future)

For better performance, we can convert Demucs to ONNX:

```bash
pip install onnxruntime
# Then modify termux_server.py to use ONNX instead of PyTorch
```

The ONNX Runtime can use XNNPACK for ARM64 optimization.
