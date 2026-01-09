#!/usr/bin/env python3
"""Configure VDJ GPU Proxy registry settings."""

import argparse
import sys
import winreg

REG_KEY = r"Software\VDJ-GPU-Proxy"


def get_config():
    """Read current configuration."""
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_KEY) as key:
            config = {}
            try:
                config["TunnelUrl"], _ = winreg.QueryValueEx(key, "TunnelUrl")
            except FileNotFoundError:
                config["TunnelUrl"] = ""
            try:
                config["ServerAddress"], _ = winreg.QueryValueEx(key, "ServerAddress")
            except FileNotFoundError:
                config["ServerAddress"] = "127.0.0.1"
            try:
                config["ServerPort"], _ = winreg.QueryValueEx(key, "ServerPort")
            except FileNotFoundError:
                config["ServerPort"] = 50051
            try:
                config["Enabled"], _ = winreg.QueryValueEx(key, "Enabled")
            except FileNotFoundError:
                config["Enabled"] = 1
            return config
    except FileNotFoundError:
        return None


def set_config(tunnel_url=None, server_address=None, server_port=None, enabled=None):
    """Set configuration values."""
    with winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_KEY) as key:
        if tunnel_url is not None:
            winreg.SetValueEx(key, "TunnelUrl", 0, winreg.REG_SZ, tunnel_url)
        if server_address is not None:
            winreg.SetValueEx(key, "ServerAddress", 0, winreg.REG_SZ, server_address)
        if server_port is not None:
            winreg.SetValueEx(key, "ServerPort", 0, winreg.REG_DWORD, int(server_port))
        if enabled is not None:
            winreg.SetValueEx(key, "Enabled", 0, winreg.REG_DWORD, int(enabled))


def main():
    parser = argparse.ArgumentParser(description="Configure VDJ GPU Proxy")
    parser.add_argument(
        "--tunnel-url",
        default=None,
        help="Cloudflare tunnel URL (e.g., https://vdj-gpu-direct.ai-smith.net)",
    )
    parser.add_argument(
        "--server",
        default=None,
        help="Direct server address (for LAN, e.g., 192.168.1.100)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=None,
        help="Direct server port (default: 50051)",
    )
    parser.add_argument(
        "--disable",
        action="store_true",
        help="Disable the proxy (fallback to local)",
    )
    parser.add_argument(
        "--enable",
        action="store_true",
        help="Enable the proxy",
    )
    parser.add_argument(
        "--show",
        action="store_true",
        help="Show current configuration",
    )
    args = parser.parse_args()

    if args.show:
        config = get_config()
        print("VDJ GPU Proxy Configuration")
        print("=" * 40)
        if config:
            print(f"  Tunnel URL:     {config['TunnelUrl']}")
            print(f"  Server Address: {config['ServerAddress']}")
            print(f"  Server Port:    {config['ServerPort']}")
            print(f"  Enabled:        {'Yes' if config['Enabled'] else 'No'}")
        else:
            print("  (No configuration found - using defaults)")
        return 0

    # Apply settings
    if args.tunnel_url:
        set_config(tunnel_url=args.tunnel_url, enabled=1)
        print(f"Set tunnel URL: {args.tunnel_url}")

    if args.server:
        set_config(server_address=args.server)
        print(f"Set server address: {args.server}")

    if args.port:
        set_config(server_port=args.port)
        print(f"Set server port: {args.port}")

    if args.disable:
        set_config(enabled=0)
        print("Proxy disabled")

    if args.enable:
        set_config(enabled=1)
        print("Proxy enabled")

    # If no args, set default tunnel URL
    if not any([args.tunnel_url, args.server, args.port, args.disable, args.enable, args.show]):
        default_url = "https://vdj-gpu-direct.ai-smith.net"
        set_config(tunnel_url=default_url, enabled=1)
        print(f"Configured with default tunnel URL: {default_url}")

    print()
    print("Restart VirtualDJ for changes to take effect.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
