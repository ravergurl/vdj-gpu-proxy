#!/usr/bin/env python3
"""Install VDJ GPU Proxy DLL."""

import os
import shutil
import subprocess
import sys
from pathlib import Path


def main():
    # Paths
    user_home = Path.home()
    vdj_drivers = user_home / "AppData" / "Local" / "VirtualDJ" / "Drivers"
    target_dll = vdj_drivers / "ml1151.dll"
    backup_dll = vdj_drivers / "ml1151_real.dll"
    source_dll = Path(__file__).parent.parent / "artifacts" / "onnxruntime.dll"

    print("VDJ GPU Proxy Installer")
    print("=" * 40)

    # Check source DLL exists
    if not source_dll.exists():
        print(f"ERROR: Source DLL not found: {source_dll}")
        print("Run GitHub Actions build first or download artifact")
        return 1

    # Create drivers folder if needed
    if not vdj_drivers.exists():
        print(f"Creating directory: {vdj_drivers}")
        vdj_drivers.mkdir(parents=True)

    # Backup original if not already done
    if not backup_dll.exists():
        if target_dll.exists():
            print(f"Backing up original ml1151.dll...")
            shutil.copy2(target_dll, backup_dll)
            print(f"  Saved to: {backup_dll}")
        else:
            print("WARNING: Original ml1151.dll not found")
            print("  VirtualDJ might create it on first run with stems")

    # Kill VirtualDJ if running
    try:
        result = subprocess.run(
            ["taskkill", "/f", "/im", "virtualdj.exe"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            print("Stopped VirtualDJ process")
    except Exception:
        pass

    # Install proxy DLL
    print(f"Installing proxy DLL...")
    print(f"  Source: {source_dll}")
    print(f"  Target: {target_dll}")
    shutil.copy2(source_dll, target_dll)

    print()
    print("Installation complete!")
    print()
    print("Next steps:")
    print("1. Run: python scripts/setup_registry.py")
    print("2. Start VirtualDJ")
    print("3. Load a track and enable stems separation")
    print("4. Check DebugView for 'VDJ-GPU-Proxy' messages")

    return 0


if __name__ == "__main__":
    sys.exit(main())
