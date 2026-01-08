#!/usr/bin/env python3
"""
VDJ-GPU-Proxy Monitor

Shows real-time proxy activity. Keep this window open while using VirtualDJ.
"""

import os
import sys
import time
from datetime import datetime
from pathlib import Path

try:
    import winreg
except ImportError:
    print("This tool only runs on Windows.")
    sys.exit(1)

LOG_DIR = Path(os.environ.get("LOCALAPPDATA", "")) / "VDJ-GPU-Proxy"
REG_PATH = r"Software\VDJ-GPU-Proxy"


class Colors:
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    CYAN = "\033[0;36m"
    MAGENTA = "\033[0;35m"
    DIM = "\033[2m"
    NC = "\033[0m"


os.system("")


def get_config() -> dict:
    config = {
        "enabled": False,
        "tunnel_url": "",
        "server_address": "",
        "server_port": 50051,
    }
    try:
        with winreg.OpenKey(winreg.HKEY_CURRENT_USER, REG_PATH) as key:
            try:
                config["enabled"] = winreg.QueryValueEx(key, "Enabled")[0] == 1
            except FileNotFoundError:
                pass
            try:
                config["tunnel_url"] = winreg.QueryValueEx(key, "TunnelUrl")[0]
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
    except FileNotFoundError:
        pass
    return config


def check_vdj_installation() -> dict:
    result = {"path": None, "proxy_installed": False, "real_dll": False}
    paths = [
        Path(os.environ.get("ProgramFiles", "")) / "VirtualDJ",
        Path(os.environ.get("ProgramFiles(x86)", "")) / "VirtualDJ",
        Path(os.environ.get("LOCALAPPDATA", "")) / "VirtualDJ",
    ]
    for path in paths:
        if (path / "VirtualDJ.exe").exists():
            result["path"] = path
            result["proxy_installed"] = (path / "onnxruntime.dll").exists()
            result["real_dll"] = (path / "onnxruntime_real.dll").exists()
            break
    return result


def get_latest_log() -> Path | None:
    if not LOG_DIR.exists():
        return None
    logs = sorted(LOG_DIR.glob("*.log"), key=lambda p: p.stat().st_mtime, reverse=True)
    return logs[0] if logs else None


def tail_log(log_path: Path, last_pos: int) -> tuple[list[str], int]:
    try:
        size = log_path.stat().st_size
        if size < last_pos:
            last_pos = 0

        with open(log_path, "r", encoding="utf-8", errors="ignore") as f:
            f.seek(last_pos)
            lines = f.readlines()
            new_pos = f.tell()

        return lines, new_pos
    except Exception:
        return [], last_pos


def format_log_line(line: str) -> str:
    line = line.strip()
    if not line:
        return ""

    if "Connected to GPU server" in line:
        return f"{Colors.GREEN}>>> {line}{Colors.NC}"
    elif "Remote inference successful" in line:
        return f"{Colors.GREEN}[OK] {line}{Colors.NC}"
    elif "Connecting" in line:
        return f"{Colors.CYAN}[..] {line}{Colors.NC}"
    elif "error" in line.lower() or "failed" in line.lower():
        return f"{Colors.RED}[!!] {line}{Colors.NC}"
    elif "fallback" in line.lower():
        return f"{Colors.YELLOW}[FB] {line}{Colors.NC}"
    elif "HookedRun" in line:
        return f"{Colors.MAGENTA}[>>] Inference request{Colors.NC}"
    else:
        return f"{Colors.DIM}{line}{Colors.NC}"


def clear_screen():
    os.system("cls" if os.name == "nt" else "clear")


def main():
    clear_screen()

    print()
    print(
        f"{Colors.CYAN}╔══════════════════════════════════════════════════════════╗{Colors.NC}"
    )
    print(
        f"{Colors.CYAN}║            VDJ-GPU-Proxy Monitor                         ║{Colors.NC}"
    )
    print(
        f"{Colors.CYAN}║                                                          ║{Colors.NC}"
    )
    print(
        f"{Colors.CYAN}║  Keep this window open while using VirtualDJ             ║{Colors.NC}"
    )
    print(
        f"{Colors.CYAN}║  Press Ctrl+C to exit                                    ║{Colors.NC}"
    )
    print(
        f"{Colors.CYAN}╚══════════════════════════════════════════════════════════╝{Colors.NC}"
    )
    print()

    config = get_config()
    vdj = check_vdj_installation()

    print(f"{Colors.CYAN}Configuration:{Colors.NC}")
    print(f"  Enabled: ", end="")
    print(
        f"{Colors.GREEN}YES{Colors.NC}"
        if config["enabled"]
        else f"{Colors.RED}NO{Colors.NC}"
    )

    if config["tunnel_url"]:
        print(f"  Mode:    {Colors.MAGENTA}TUNNEL{Colors.NC}")
        print(f"  URL:     {config['tunnel_url']}")
    elif config["server_address"]:
        print(f"  Mode:    DIRECT")
        print(f"  Server:  {config['server_address']}:{config['server_port']}")
    else:
        print(f"  Mode:    {Colors.YELLOW}NOT CONFIGURED{Colors.NC}")

    print()
    print(f"{Colors.CYAN}Installation:{Colors.NC}")
    if vdj["path"]:
        print(f"  VirtualDJ: {vdj['path']}")
        print(f"  Proxy DLL: ", end="")
        print(
            f"{Colors.GREEN}OK{Colors.NC}"
            if vdj["proxy_installed"]
            else f"{Colors.RED}MISSING{Colors.NC}"
        )
        print(f"  Real DLL:  ", end="")
        print(
            f"{Colors.GREEN}OK{Colors.NC}"
            if vdj["real_dll"]
            else f"{Colors.RED}MISSING{Colors.NC}"
        )

        if not vdj["real_dll"]:
            print()
            print(f"{Colors.RED}ERROR: onnxruntime_real.dll is missing!{Colors.NC}")
            print(f"The proxy cannot work without the original ONNX Runtime.")
            print(f"Run the install script again or copy it manually.")
    else:
        print(f"  {Colors.YELLOW}VirtualDJ not found{Colors.NC}")

    print()
    print(f"{Colors.CYAN}{'═' * 60}{Colors.NC}")
    print(f"{Colors.CYAN}Live Log (waiting for activity...):{Colors.NC}")
    print()

    log_path = get_latest_log()
    last_pos = 0
    last_activity = None
    inference_count = 0

    if log_path:
        last_pos = log_path.stat().st_size

    try:
        while True:
            log_path = get_latest_log()

            if log_path:
                lines, last_pos = tail_log(log_path, last_pos)

                for line in lines:
                    formatted = format_log_line(line)
                    if formatted:
                        timestamp = datetime.now().strftime("%H:%M:%S")
                        print(f"{Colors.DIM}[{timestamp}]{Colors.NC} {formatted}")
                        last_activity = time.time()

                        if "successful" in line.lower() or "HookedRun" in line:
                            inference_count += 1

            if last_activity:
                elapsed = time.time() - last_activity
                if elapsed > 30:
                    status = f"{Colors.DIM}[No activity for {int(elapsed)}s]{Colors.NC}"
                    print(f"\r{status}", end="", flush=True)

            time.sleep(0.5)

    except KeyboardInterrupt:
        print()
        print()
        print(f"{Colors.CYAN}Session Summary:{Colors.NC}")
        print(f"  Inference requests: {inference_count}")
        print()
        print("Goodbye!")


if __name__ == "__main__":
    main()
