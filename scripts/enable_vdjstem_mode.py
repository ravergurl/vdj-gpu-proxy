#!/usr/bin/env python3
"""
Enable VDJStem mode for VDJ GPU Proxy.

When enabled, the proxy will:
1. Create .vdjstem files (MP4 with all 4 stems)
2. Save them to the configured stems folder
3. Also return tensors for immediate use

Usage:
    python enable_vdjstem_mode.py [--enable|--disable] [--stems-folder PATH]
"""

import argparse
import os
import sys

try:
    import winreg
except ImportError:
    print("This script requires Windows")
    sys.exit(1)


REG_KEY = r"Software\VDJ-GPU-Proxy"


def get_default_stems_folder():
    """Get default stems folder path."""
    local_app_data = os.environ.get("LOCALAPPDATA", "C:\\")
    return os.path.join(local_app_data, "VDJ-Stems")


def enable_vdjstem_mode(stems_folder=None):
    """Enable VDJStem mode."""
    if stems_folder is None:
        stems_folder = get_default_stems_folder()

    # Create stems folder if it doesn't exist
    os.makedirs(stems_folder, exist_ok=True)

    try:
        key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_WRITE)
        winreg.SetValueEx(key, "UseVdjStemMode", 0, winreg.REG_DWORD, 1)
        winreg.SetValueEx(key, "StemsFolder", 0, winreg.REG_SZ, stems_folder)
        winreg.CloseKey(key)
        print(f"VDJStem mode ENABLED")
        print(f"Stems folder: {stems_folder}")
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False


def disable_vdjstem_mode():
    """Disable VDJStem mode."""
    try:
        key = winreg.CreateKeyEx(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_WRITE)
        winreg.SetValueEx(key, "UseVdjStemMode", 0, winreg.REG_DWORD, 0)
        winreg.CloseKey(key)
        print("VDJStem mode DISABLED")
        return True
    except Exception as e:
        print(f"Error: {e}")
        return False


def get_status():
    """Get current VDJStem mode status."""
    try:
        key = winreg.OpenKeyEx(winreg.HKEY_CURRENT_USER, REG_KEY, 0, winreg.KEY_READ)
        try:
            mode, _ = winreg.QueryValueEx(key, "UseVdjStemMode")
        except FileNotFoundError:
            mode = 0
        try:
            folder, _ = winreg.QueryValueEx(key, "StemsFolder")
        except FileNotFoundError:
            folder = get_default_stems_folder()
        winreg.CloseKey(key)
        return mode == 1, folder
    except FileNotFoundError:
        return False, get_default_stems_folder()


def main():
    parser = argparse.ArgumentParser(description="Configure VDJStem mode for VDJ GPU Proxy")
    parser.add_argument("--enable", action="store_true", help="Enable VDJStem mode")
    parser.add_argument("--disable", action="store_true", help="Disable VDJStem mode")
    parser.add_argument("--stems-folder", type=str, help="Path to stems folder")
    parser.add_argument("--status", action="store_true", help="Show current status")
    args = parser.parse_args()

    if args.status or (not args.enable and not args.disable):
        enabled, folder = get_status()
        print(f"VDJStem mode: {'ENABLED' if enabled else 'DISABLED'}")
        print(f"Stems folder: {folder}")

        # Count existing stems
        if os.path.exists(folder):
            stem_count = 0
            total_size = 0
            for root, _, files in os.walk(folder):
                for f in files:
                    if f.endswith(".vdjstem"):
                        stem_count += 1
                        total_size += os.path.getsize(os.path.join(root, f))
            print(f"Cached stems: {stem_count} files ({total_size / (1024*1024):.1f} MB)")
        return

    if args.enable:
        enable_vdjstem_mode(args.stems_folder)
    elif args.disable:
        disable_vdjstem_mode()


if __name__ == "__main__":
    main()
