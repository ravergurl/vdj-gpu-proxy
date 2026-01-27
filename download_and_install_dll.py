#!/usr/bin/env python3
"""Download and install the latest DLL artifact from GitHub Actions."""
import subprocess
import shutil
import os
from pathlib import Path

# Download artifact using gh CLI
print("Downloading artifact from GitHub Actions run 20861568049...")
result = subprocess.run(
    ["gh", "run", "download", "20861568049", "-n", "proxy-dll-windows", "-D", "proxy-dll-artifact"],
    capture_output=True,
    text=True,
    cwd=Path(__file__).parent
)

if result.returncode != 0:
    print(f"Error downloading: {result.stderr}")
    exit(1)

print("[OK] Artifact downloaded")

# Define installation paths
dll_paths = [
    Path("C:/Program Files/VirtualDJ/onnxruntime.dll"),
    Path("C:/Users/peopl/AppData/Local/VirtualDJ/Drivers/ml1151.dll")
]

artifact_dll = Path(__file__).parent / "proxy-dll-artifact" / "onnxruntime.dll"

if not artifact_dll.exists():
    print(f"Error: {artifact_dll} not found in downloaded artifact")
    exit(1)

# Install to both locations
for dll_path in dll_paths:
    if dll_path.exists():
        backup = dll_path.with_suffix('.dll.bak')
        print(f"Backing up {dll_path} -> {backup}")
        shutil.copy2(dll_path, backup)

    print(f"Installing to {dll_path}")
    dll_path.parent.mkdir(parents=True, exist_ok=True)
    shutil.copy2(artifact_dll, dll_path)
    print(f"[OK] Installed to {dll_path}")

print("\n[OK] DLL installation complete!")
print("Artifact location:", Path(__file__).parent / "proxy-dll-artifact")
