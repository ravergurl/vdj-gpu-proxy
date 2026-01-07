# VDJ-GPU-Proxy

Offload VirtualDJ's stems separation to a remote GPU server via gRPC.

## Architecture

```
+---------------------------+     gRPC      +---------------------------+
|   Local PC (VirtualDJ)    |<------------->|  GPU Server (Demucs)      |
|   onnxruntime.dll proxy   |               |  RTX 3080/4080/etc        |
+---------------------------+               +---------------------------+
```

The proxy DLL intercepts VirtualDJ's ONNX Runtime inference calls and forwards them to a remote GPU server running Demucs for real-time stems separation.

## Requirements

### Local (VirtualDJ) Machine
- Windows 10/11 (x64)
- VirtualDJ 2023+
- Network access to GPU server

### GPU Server
- Linux (Ubuntu 20.04+ recommended) or Windows with WSL2
- NVIDIA GPU with 8GB+ VRAM (RTX 3080+ recommended)
- CUDA 11.8+ and cuDNN
- Python 3.10+

## Quick Start

### Option 1: One-Click Setup

**Windows (Local PC):**
```powershell
git clone https://github.com/ravergurl/vdj-gpu-proxy.git
cd vdj-gpu-proxy
.\scripts\setup-windows.ps1
```

**Linux (GPU Server):**
```bash
git clone https://github.com/ravergurl/vdj-gpu-proxy.git
cd vdj-gpu-proxy
./scripts/setup-server.sh
```

### Option 2: Manual Setup

#### 1. Setup GPU Server (Linux)

```bash
git clone https://github.com/ravergurl/vdj-gpu-proxy.git
cd vdj-gpu-proxy/server

# Using uv (recommended)
uv venv && source .venv/bin/activate
uv pip install -e ".[dev]"

# Or using pip
python3 -m venv .venv && source .venv/bin/activate
pip install -e ".[dev]"

# Generate proto files
cd .. && python scripts/generate_proto.py

# Start server
vdj-stems-server --host 0.0.0.0 --port 50051
```

#### 2. Build & Install Proxy DLL (Windows)

```powershell
# Install vcpkg dependencies
vcpkg install grpc:x64-windows protobuf:x64-windows gtest:x64-windows

# Build
cmake -B build -S . -DCMAKE_TOOLCHAIN_FILE="$env:VCPKG_ROOT/scripts/buildsystems/vcpkg.cmake"
cmake --build build --config Release

# Install to VirtualDJ
.\scripts\install_proxy.ps1 -ServerAddress "192.168.1.100" -ServerPort 50051
```

#### 3. Launch VirtualDJ

Stems separation now runs on your remote GPU!

## CLI Tools

### Windows Control Tool (vdj-proxy-ctl.ps1)

Manage the proxy from the command line:

```powershell
# Check status
.\scripts\vdj-proxy-ctl.ps1 status

# Enable/disable proxy
.\scripts\vdj-proxy-ctl.ps1 enable
.\scripts\vdj-proxy-ctl.ps1 disable

# Configure server
.\scripts\vdj-proxy-ctl.ps1 config -ServerAddress 192.168.1.100 -ServerPort 50051

# Test connection
.\scripts\vdj-proxy-ctl.ps1 test

# View logs
.\scripts\vdj-proxy-ctl.ps1 logs
```

### Server CLI Tools (Linux/GPU Server)

```bash
# Health check
vdj-stems-health --host 127.0.0.1 --port 50051

# Get server status (supports --json)
vdj-stems-status --host 127.0.0.1 --port 50051
vdj-stems-status --json  # For scripting

# Benchmark performance
vdj-stems-benchmark --host 127.0.0.1 --duration 10 --iterations 5
```

## Configuration

### Windows Registry

Settings are stored at `HKCU:\Software\VDJ-GPU-Proxy`:

| Key | Type | Default | Description |
|-----|------|---------|-------------|
| `ServerAddress` | String | `127.0.0.1` | GPU server IP/hostname |
| `ServerPort` | DWORD | `50051` | gRPC port |
| `Enabled` | DWORD | `1` | 1=enabled, 0=disabled (fallback to local) |

### Environment Variables (Server)

| Variable | Default | Description |
|----------|---------|-------------|
| `VDJ_STEMS_MODEL` | `htdemucs` | Demucs model to use |
| `VDJ_STEMS_DEVICE` | `cuda` | Device: `cuda` or `cpu` |
| `VDJ_STEMS_LOG_LEVEL` | `INFO` | Logging level |

## Testing

### Run C++ Tests (Windows)

```powershell
# Build with tests enabled
cmake -B build -S . -DBUILD_TESTS=ON -DCMAKE_TOOLCHAIN_FILE="$env:VCPKG_ROOT/scripts/buildsystems/vcpkg.cmake"
cmake --build build --config Release

# Run tests
cd build && ctest -C Release -V
```

### Run Python Tests (Server)

```bash
cd server
pytest tests/ -v

# With coverage
pytest tests/ --cov=src/vdj_stems_server --cov-report=html
```

## Logging

### Proxy DLL Logs

Logs are written to `%LOCALAPPDATA%\VDJ-GPU-Proxy\`:
- `vdj_gpu_proxy_YYYYMMDD.log` - Daily log files
- Includes timestamps, file:line, and performance metrics

View logs quickly:
```powershell
.\scripts\vdj-proxy-ctl.ps1 logs
```

### Server Logs

Use verbose mode for detailed logging:
```bash
vdj-stems-server -v --host 0.0.0.0 --port 50051
```

## Troubleshooting

### Proxy DLL not loading

1. **Check file placement:**
   - `onnxruntime.dll` (our proxy) should be in VirtualDJ folder
   - `onnxruntime_real.dll` (original) should exist alongside it

2. **Check VirtualDJ version:**
   - Must be VirtualDJ 2023+ that uses `onnxruntime.dll`

3. **Check logs:**
   ```powershell
   .\scripts\vdj-proxy-ctl.ps1 logs
   ```

4. **Use DebugView (SysInternals):**
   - Filter for `VDJ-GPU-Proxy` to see debug output

### Connection errors

1. **Test connectivity:**
   ```powershell
   .\scripts\vdj-proxy-ctl.ps1 test
   ```

2. **Check server is running:**
   ```bash
   vdj-stems-health --host <server_ip> --port 50051
   ```

3. **Firewall rules:**
   - Ensure port 50051 (or your configured port) is open
   - On Linux: `sudo ufw allow 50051/tcp`
   - On Windows Server: Add inbound rule for the port

4. **Network latency:**
   - Run benchmark to check RTF (Real-Time Factor)
   - RTF > 1.0 means real-time capable
   ```bash
   vdj-stems-benchmark --host <server_ip> --duration 5
   ```

### Performance issues

1. **Check GPU utilization:**
   ```bash
   nvidia-smi -l 1  # Monitor GPU usage
   ```

2. **Use wired connection:**
   - Wi-Fi adds latency and jitter
   - Gigabit Ethernet recommended

3. **Reduce audio buffer:**
   - Smaller buffers = lower latency but higher CPU
   - VirtualDJ: Options > Audio > Latency

4. **Check model selection:**
   - `htdemucs` is fastest
   - `htdemucs_ft` is higher quality but slower

### Server crashes / Out of memory

1. **Monitor GPU memory:**
   ```bash
   nvidia-smi
   ```

2. **Use smaller batches:**
   - Server automatically handles this, but very long audio chunks may OOM
   - RTX 3080 (10GB) handles most cases
   - RTX 4090 (24GB) handles everything

## Uninstall

### Windows (Proxy DLL)

```powershell
.\scripts\uninstall_proxy.ps1
```

Or manually:
1. Close VirtualDJ
2. Delete `onnxruntime.dll` from VirtualDJ folder
3. Rename `onnxruntime_real.dll` back to `onnxruntime.dll`
4. Delete registry key `HKCU:\Software\VDJ-GPU-Proxy`

### Linux (Server)

```bash
cd server
pip uninstall vdj-stems-server
rm -rf .venv
```

## Building from Source

### Prerequisites

**Windows:**
- Visual Studio 2019+ with C++ workload
- CMake 3.20+
- vcpkg
- Git

**Linux:**
- Python 3.10+
- pip or uv

### Full Build

```powershell
# Windows - full build with vcpkg setup
.\scripts\setup-windows.ps1

# Linux - full server setup
./scripts/setup-server.sh
```

### Development Build

```powershell
# Windows - skip vcpkg if already installed
.\scripts\setup-windows.ps1 -SkipVcpkg

# Clean rebuild
.\scripts\setup-windows.ps1 -Clean
```

## Project Structure

```
vdj-gpu-proxy/
+-- proxy-dll/              # Windows DLL (C++)
|   +-- src/
|       +-- dllmain.cpp     # DLL entry point
|       +-- ort_hooks.cpp   # ONNX Runtime hooks
|       +-- grpc_client.cpp # gRPC client
|       +-- tensor_utils.cpp
|       +-- logger.cpp      # File logging
+-- server/                 # GPU Server (Python)
|   +-- src/vdj_stems_server/
|       +-- main.py         # Server entry point
|       +-- inference.py    # Demucs inference engine
|       +-- grpc_server.py  # gRPC service
|       +-- cli.py          # CLI tools
|   +-- tests/              # pytest tests
+-- proto/                  # gRPC definitions
|   +-- stems.proto
+-- scripts/
|   +-- setup-windows.ps1   # Windows one-click setup
|   +-- setup-server.sh     # Linux one-click setup
|   +-- vdj-proxy-ctl.ps1   # Windows CLI tool
|   +-- install_proxy.ps1   # Install DLL to VDJ
|   +-- generate_proto.py   # Proto generation
+-- tests/                  # C++ tests (Google Test)
```

## License

MIT
