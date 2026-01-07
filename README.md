# VDJ-GPU-Proxy

Offload VirtualDJ's stems separation to a remote GPU server via gRPC.

## Architecture

```
┌─────────────────────────┐     gRPC      ┌─────────────────────────┐
│   Local PC (VirtualDJ)  │◄─────────────►│  GPU Server (Demucs)    │
│   onnxruntime.dll proxy │               │  RTX 3080/4080          │
└─────────────────────────┘               └─────────────────────────┘
```

## Requirements

### Local (VirtualDJ) Machine
- Windows 10/11
- VirtualDJ 2023+
- Network access to GPU server

### GPU Server
- Linux (Ubuntu 20.04+ recommended)
- NVIDIA GPU with 8GB+ VRAM
- CUDA 11.8+
- Python 3.10+

## Quick Start

### 1. Setup GPU Server

```bash
git clone https://github.com/ravergurl/vdj-gpu-proxy.git
cd vdj-gpu-proxy
./scripts/install_server.sh
vdj-stems-server --host 0.0.0.0 --port 50051
```

### 2. Install Proxy DLL (Windows)

```powershell
.\scripts\install_proxy.ps1 -ServerAddress "192.168.1.100" -ServerPort 50051
```

### 3. Launch VirtualDJ

Stems separation now runs on remote GPU!

## Configuration

Registry settings at `HKCU:\Software\VDJ-GPU-Proxy`:
- `ServerAddress` - GPU server IP/hostname
- `ServerPort` - gRPC port (default: 50051)
- `Enabled` - 1 to enable, 0 to disable

## Uninstall

```powershell
.\scripts\uninstall_proxy.ps1
```

## Building from Source

### Proxy DLL (Windows)

Requires: Visual Studio 2022, vcpkg, CMake

```powershell
vcpkg install grpc:x64-windows protobuf:x64-windows
cmake -B build -S . -DCMAKE_TOOLCHAIN_FILE="$env:VCPKG_ROOT/scripts/buildsystems/vcpkg.cmake"
cmake --build build --config Release
```

### Server (Linux)

```bash
cd server
pip install -e .
python ../scripts/generate_proto.py
```

## Troubleshooting

### Proxy DLL not loading
- Ensure `onnxruntime_real.dll` exists in the VirtualDJ folder.
- Check if VirtualDJ version is compatible (it must use `onnxruntime.dll`).
- Check DebugView (sysinternals) for log messages from `VDJ-GPU-Proxy`.

### Connection errors
- Verify the GPU server is running and accessible over the network.
- Check firewall settings on both machines (port 50051).
- Ensure `ServerAddress` in registry is correct.

### Performance issues
- Stems separation depends on network latency and GPU speed.
- Using a wired connection instead of Wi-Fi is highly recommended.

## License

MIT
