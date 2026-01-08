#!/usr/bin/env python3
"""
VDJ-GPU-Proxy Control Tool

Interactive CLI to configure the VDJ GPU proxy connection.
Just run it and paste your tunnel URL.
"""

import os
import socket
import ssl
import sys
import urllib.request
from pathlib import Path

try:
    import winreg
except ImportError:
    print("This tool only runs on Windows.")
    sys.exit(1)

REG_PATH = r"Software\VDJ-GPU-Proxy"
LOG_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / "VDJ-GPU-Proxy"


class Colors:
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    CYAN = "\033[0;36m"
    MAGENTA = "\033[0;35m"
    NC = "\033[0m"

    @staticmethod
    def disable():
        Colors.RED = Colors.GREEN = Colors.YELLOW = ""
        Colors.CYAN = Colors.MAGENTA = Colors.NC = ""


if os.name == "nt" and not os.environ.get("WT_SESSION"):
    try:
        os.system("")
    except:
        Colors.disable()


def get_config() -> dict:
    config = {
        "enabled": False,
        "server_address": "",
        "server_port": 50051,
        "tunnel_url": "",
        "use_tunnel": False,
    }

    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH) as key:
            try:
                config["enabled"] = winreg.QueryValueEx(key, "Enabled")[0] == 1
            except FileNotFoundError:
                pass
            try:
                config["server_address"] = winreg.QueryValueEx(key, "ServerAddress")[0]
            except FileNotFoundError:
                pass
            try:
                config["server_port"] = winreg.QueryValueEx(key, "ServerPort")[0]
            except FileNotFoundError:
                pass
            try:
                tunnel_url = winreg.QueryValueEx(key, "TunnelUrl")[0]
                if tunnel_url:
                    config["tunnel_url"] = tunnel_url
                    config["use_tunnel"] = True
            except FileNotFoundError:
                pass
    except FileNotFoundError:
        pass

    return config


def set_registry_value(name: str, value, value_type=winreg.REG_SZ):
    try:
        key = winreg.CreateKey(winreg.HKEY_CURRENT_USER, REG_PATH)
        winreg.SetValueEx(key, name, 0, value_type, value)
        winreg.CloseKey(key)
        return True
    except Exception as e:
        print(f"{Colors.RED}Error: {e}{Colors.NC}")
        return False


def get_vdj_path() -> Path | None:
    paths = [
        Path(os.environ.get("ProgramFiles", "")) / "VirtualDJ",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "VirtualDJ",
        Path(os.environ.get("LOCALAPPDATA", "")) / "VirtualDJ",
    ]
    for path in paths:
        if (path / "VirtualDJ.exe").exists():
            return path
    return None


def test_tunnel(url: str) -> bool:
    if not url:
        return False
    try:
        ctx = ssl.create_default_context()
        req = urllib.request.Request(url, method="HEAD")
        urllib.request.urlopen(req, timeout=5, context=ctx)
        return True
    except urllib.error.HTTPError:
        return True
    except Exception:
        return False


def test_direct(address: str, port: int) -> bool:
    if not address:
        return False
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(3)
        sock.connect((address, port))
        sock.close()
        return True
    except:
        return False


def show_status():
    config = get_config()

    print()
    print(f"  Enabled: ", end="")
    print(
        f"{Colors.GREEN}YES{Colors.NC}"
        if config["enabled"]
        else f"{Colors.RED}NO{Colors.NC}"
    )

    if config["use_tunnel"]:
        print(f"  Mode:    {Colors.MAGENTA}TUNNEL{Colors.NC}")
        print(f"  URL:     {config['tunnel_url']}")
    elif config["server_address"]:
        print(f"  Mode:    DIRECT")
        print(f"  Server:  {config['server_address']}:{config['server_port']}")
    else:
        print(f"  Mode:    {Colors.YELLOW}NOT CONFIGURED{Colors.NC}")

    vdj = get_vdj_path()
    if vdj:
        installed = (vdj / "onnxruntime_real.dll").exists()
        print(f"  Proxy:   ", end="")
        print(
            f"{Colors.GREEN}INSTALLED{Colors.NC}"
            if installed
            else f"{Colors.YELLOW}NOT INSTALLED{Colors.NC}"
        )


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def main():
    clear_screen()

    print()
    print(f"{Colors.CYAN}╔══════════════════════════════════════════╗{Colors.NC}")
    print(f"{Colors.CYAN}║      VDJ-GPU-Proxy Configuration         ║{Colors.NC}")
    print(f"{Colors.CYAN}╚══════════════════════════════════════════╝{Colors.NC}")

    show_status()

    print()
    print(f"{Colors.CYAN}─────────────────────────────────────────────{Colors.NC}")
    print()

    config = get_config()

    if config["use_tunnel"] and config["tunnel_url"]:
        print(f"Current tunnel: {config['tunnel_url']}")
        print()
        choice = input("Enter new URL, or press Enter to test current: ").strip()

        if not choice:
            print()
            print("Testing connection...", end=" ", flush=True)
            if test_tunnel(config["tunnel_url"]):
                print(f"{Colors.GREEN}OK{Colors.NC}")
                print()
                print(f"{Colors.GREEN}Ready! Launch VirtualDJ.{Colors.NC}")
            else:
                print(f"{Colors.RED}FAILED{Colors.NC}")
                print()
                print("The tunnel may have expired. Get a new URL from the server.")
            print()
            input("Press Enter to exit...")
            return
        else:
            tunnel_url = choice
    else:
        print("Paste the tunnel URL from your GPU server:")
        print(
            f"{Colors.YELLOW}(looks like: https://random-words.trycloudflare.com){Colors.NC}"
        )
        print()
        tunnel_url = input("URL: ").strip()

    if not tunnel_url:
        print()
        print(f"{Colors.YELLOW}No URL entered. Exiting.{Colors.NC}")
        return

    if not tunnel_url.startswith("https://"):
        tunnel_url = "https://" + tunnel_url

    if "trycloudflare.com" not in tunnel_url:
        print()
        print(f"{Colors.RED}Invalid URL format.{Colors.NC}")
        print("Expected something like: https://xxx-yyy.trycloudflare.com")
        print()
        input("Press Enter to exit...")
        return

    tunnel_url = tunnel_url.rstrip("/")

    print()
    print("Testing connection...", end=" ", flush=True)

    if test_tunnel(tunnel_url):
        print(f"{Colors.GREEN}OK{Colors.NC}")
        print()

        set_registry_value("TunnelUrl", tunnel_url)
        set_registry_value("ServerAddress", "")
        set_registry_value("ServerPort", 443, winreg.REG_DWORD)
        set_registry_value("Enabled", 1, winreg.REG_DWORD)

        print(f"{Colors.GREEN}Configuration saved!{Colors.NC}")
        print()
        print(f"Tunnel URL: {tunnel_url}")
        print(f"Proxy:      ENABLED")
        print()
        print(f"{Colors.GREEN}Ready! Launch VirtualDJ to use GPU stems.{Colors.NC}")
    else:
        print(f"{Colors.RED}FAILED{Colors.NC}")
        print()
        print("Could not connect to the tunnel.")
        print()
        print("Check that:")
        print("  1. The URL is correct")
        print("  2. The GPU server is running")
        print("  3. Run on server: sudo python deploy.py status")

    print()
    input("Press Enter to exit...")


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        print()
        print("Cancelled.")
