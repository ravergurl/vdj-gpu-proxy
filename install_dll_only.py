#!/usr/bin/env python3
"""Install the DLL from artifact directory."""
import shutil
from pathlib import Path

# Define installation paths
dll_paths = [
    Path("C:/Program Files/VirtualDJ/onnxruntime.dll"),
    Path("C:/Users/peopl/AppData/Local/VirtualDJ/Drivers/ml1151.dll")
]

artifact_dll = Path(__file__).parent / "proxy-dll-artifact" / "onnxruntime.dll"

if not artifact_dll.exists():
    print(f"Error: {artifact_dll} not found")
    exit(1)

print(f"Found DLL: {artifact_dll} ({artifact_dll.stat().st_size} bytes)")

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
