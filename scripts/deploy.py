#!/usr/bin/env python3
"""
VDJ Stems Server Deployment Script

Deploys the GPU inference server with optional Cloudflare Tunnel for remote access.
Handles venv detection, dependency management, and systemd service creation.

Usage:
    python deploy.py install          # Install server and dependencies
    python deploy.py start            # Start server (with tunnel if configured)
    python deploy.py stop             # Stop server
    python deploy.py status           # Show status
    python deploy.py tunnel           # Start tunnel only (shows URL)
    python deploy.py uninstall        # Remove everything
"""

from __future__ import annotations

import argparse
import json
import os
import platform
import re
import shutil
import subprocess
import sys
import tempfile
import time
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

# ============================================================================
# Configuration
# ============================================================================

SERVICE_NAME = "vdj-stems-server"
TUNNEL_SERVICE_NAME = "vdj-stems-tunnel"
INSTALL_DIR = Path("/opt/vdj-stems-server")
CONFIG_FILE = INSTALL_DIR / "config.json"
TUNNEL_URL_FILE = INSTALL_DIR / "tunnel_url.txt"
CLOUDFLARED_PATH = Path("/usr/local/bin/cloudflared")

MIN_PYTHON_VERSION = (3, 10)
GRPC_PORT = 50051


# ============================================================================
# Logging
# ============================================================================


class Colors:
    RED = "\033[0;31m"
    GREEN = "\033[0;32m"
    YELLOW = "\033[1;33m"
    BLUE = "\033[0;34m"
    CYAN = "\033[0;36m"
    NC = "\033[0m"  # No Color


def log(msg: str) -> None:
    print(f"{Colors.GREEN}[+]{Colors.NC} {msg}")


def warn(msg: str) -> None:
    print(f"{Colors.YELLOW}[!]{Colors.NC} {msg}")


def error(msg: str, exit_code: int = 1) -> None:
    print(f"{Colors.RED}[x]{Colors.NC} {msg}", file=sys.stderr)
    if exit_code:
        sys.exit(exit_code)


def info(msg: str) -> None:
    print(f"{Colors.CYAN}[i]{Colors.NC} {msg}")


# ============================================================================
# System Detection
# ============================================================================


@dataclass
class SystemInfo:
    """Detected system information."""

    os_name: str = ""
    os_version: str = ""
    python_version: tuple = field(default_factory=tuple)
    has_systemd: bool = False
    has_nvidia_gpu: bool = False
    gpu_name: str = ""
    gpu_memory_mb: int = 0
    has_uv: bool = False
    has_cloudflared: bool = False
    is_root: bool = False


def detect_system() -> SystemInfo:
    """Detect system capabilities and configuration."""
    info = SystemInfo()

    # OS info
    info.os_name = platform.system()
    info.os_version = platform.release()
    info.python_version = sys.version_info[:3]
    info.is_root = os.geteuid() == 0 if hasattr(os, "geteuid") else False

    # systemd
    info.has_systemd = Path("/run/systemd/system").exists()

    # uv
    info.has_uv = shutil.which("uv") is not None

    # cloudflared
    info.has_cloudflared = (
        shutil.which("cloudflared") is not None or CLOUDFLARED_PATH.exists()
    )

    # NVIDIA GPU
    try:
        result = subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=name,memory.total",
                "--format=csv,noheader,nounits",
            ],
            capture_output=True,
            text=True,
            timeout=5,
        )
        if result.returncode == 0 and result.stdout.strip():
            parts = result.stdout.strip().split(",")
            info.has_nvidia_gpu = True
            info.gpu_name = parts[0].strip()
            info.gpu_memory_mb = int(float(parts[1].strip())) if len(parts) > 1 else 0
    except (subprocess.TimeoutExpired, FileNotFoundError, ValueError):
        pass

    return info


# ============================================================================
# Project Detection
# ============================================================================


def find_project_root(start_path: Optional[Path] = None) -> Optional[Path]:
    """Find the project root directory containing server/ and proto/."""
    if start_path is None:
        start_path = Path(__file__).resolve().parent

    # Check common patterns
    candidates = [
        start_path.parent,  # scripts/../
        start_path,
        Path.cwd(),
        Path.cwd().parent,
    ]

    for candidate in candidates:
        if (candidate / "server" / "pyproject.toml").exists() and (
            candidate / "proto"
        ).exists():
            return candidate.resolve()

    # Walk up from start
    current = start_path
    while current != current.parent:
        if (current / "server" / "pyproject.toml").exists() and (
            current / "proto"
        ).exists():
            return current.resolve()
        current = current.parent

    return None


# ============================================================================
# Virtual Environment Management
# ============================================================================


def get_venv_python(venv_path: Path) -> Optional[Path]:
    """Get the Python executable path for a venv."""
    if platform.system() == "Windows":
        python = venv_path / "Scripts" / "python.exe"
    else:
        python = venv_path / "bin" / "python"
    return python if python.exists() else None


def is_venv_valid(venv_path: Path) -> bool:
    """Check if a virtual environment exists and is valid."""
    python = get_venv_python(venv_path)
    if not python:
        return False

    try:
        result = subprocess.run(
            [str(python), "-c", "import sys; print(sys.version_info[:2])"],
            capture_output=True,
            text=True,
            timeout=10,
        )
        if result.returncode != 0:
            return False

        # Check Python version is compatible
        version_str = result.stdout.strip()
        # Parse "(3, 10)" format
        match = re.search(r"\((\d+),\s*(\d+)\)", version_str)
        if match:
            major, minor = int(match.group(1)), int(match.group(2))
            return (major, minor) >= MIN_PYTHON_VERSION
        return False
    except (subprocess.TimeoutExpired, FileNotFoundError):
        return False


def create_venv(venv_path: Path, use_uv: bool = False) -> bool:
    """Create a virtual environment."""
    log(f"Creating virtual environment at {venv_path}")

    try:
        if use_uv:
            subprocess.run(["uv", "venv", str(venv_path)], check=True)
        else:
            subprocess.run([sys.executable, "-m", "venv", str(venv_path)], check=True)
        return True
    except subprocess.CalledProcessError as e:
        error(f"Failed to create venv: {e}", exit_code=0)
        return False


def get_installed_packages(venv_path: Path) -> dict[str, str]:
    """Get dict of installed packages and versions in a venv."""
    python = get_venv_python(venv_path)
    if not python:
        return {}

    try:
        result = subprocess.run(
            [str(python), "-m", "pip", "list", "--format=json"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if result.returncode == 0:
            packages = json.loads(result.stdout)
            return {pkg["name"].lower(): pkg["version"] for pkg in packages}
    except (subprocess.TimeoutExpired, json.JSONDecodeError, KeyError):
        pass
    return {}


def check_package_installed(venv_path: Path, package: str) -> bool:
    """Check if a package is installed in the venv."""
    packages = get_installed_packages(venv_path)
    # Normalize package name (replace - with _, lowercase)
    normalized = package.lower().replace("-", "_").replace("_", "-")
    return normalized in packages or package.lower() in packages


def install_package(
    venv_path: Path, package: str, use_uv: bool = False, editable: bool = False
) -> bool:
    """Install a package into the venv."""
    python = get_venv_python(venv_path)
    if not python:
        return False

    try:
        if use_uv:
            cmd = ["uv", "pip", "install"]
            if editable:
                cmd.append("-e")
            cmd.append(package)
            # uv needs to know which venv
            env = os.environ.copy()
            env["VIRTUAL_ENV"] = str(venv_path)
            subprocess.run(cmd, check=True, env=env)
        else:
            cmd = [str(python), "-m", "pip", "install", "-q"]
            if editable:
                cmd.append("-e")
            cmd.append(package)
            subprocess.run(cmd, check=True)
        return True
    except subprocess.CalledProcessError:
        return False


# ============================================================================
# Dependency Management
# ============================================================================


def check_server_installed(venv_path: Path) -> bool:
    """Check if vdj-stems-server is installed and importable."""
    python = get_venv_python(venv_path)
    if not python:
        return False

    try:
        result = subprocess.run(
            [
                str(python),
                "-c",
                "import vdj_stems_server; print(vdj_stems_server.__version__)",
            ],
            capture_output=True,
            text=True,
            timeout=10,
        )
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        return False


def check_proto_generated(install_dir: Path) -> bool:
    """Check if proto files have been generated."""
    pb2_file = install_dir / "src" / "vdj_stems_server" / "stems_pb2.py"
    grpc_file = install_dir / "src" / "vdj_stems_server" / "stems_pb2_grpc.py"
    return pb2_file.exists() and grpc_file.exists()


def generate_proto(install_dir: Path, venv_path: Path) -> bool:
    """Generate proto files from stems.proto."""
    python = get_venv_python(venv_path)
    if not python:
        return False

    proto_dir = install_dir / "proto"
    proto_file = proto_dir / "stems.proto"
    output_dir = install_dir / "src" / "vdj_stems_server"

    if not proto_file.exists():
        error(f"Proto file not found: {proto_file}", exit_code=0)
        return False

    output_dir.mkdir(parents=True, exist_ok=True)

    log("Generating proto files...")
    try:
        subprocess.run(
            [
                str(python),
                "-m",
                "grpc_tools.protoc",
                f"-I{proto_dir}",
                f"--python_out={output_dir}",
                f"--grpc_python_out={output_dir}",
                f"--pyi_out={output_dir}",
                str(proto_file),
            ],
            check=True,
        )

        # Fix imports
        grpc_file = output_dir / "stems_pb2_grpc.py"
        if grpc_file.exists():
            content = grpc_file.read_text(encoding="utf-8")
            new_content = content.replace("import stems_pb2", "from . import stems_pb2")
            grpc_file.write_text(new_content, encoding="utf-8")

        return True
    except subprocess.CalledProcessError as e:
        error(f"Proto generation failed: {e}", exit_code=0)
        return False


# ============================================================================
# Cloudflare Tunnel
# ============================================================================


def install_cloudflared() -> bool:
    """Install cloudflared binary."""
    if CLOUDFLARED_PATH.exists() or shutil.which("cloudflared"):
        log("cloudflared already installed")
        return True

    log("Installing cloudflared...")

    # Detect architecture
    machine = platform.machine().lower()
    if machine in ("x86_64", "amd64"):
        arch = "amd64"
    elif machine in ("aarch64", "arm64"):
        arch = "arm64"
    elif machine.startswith("arm"):
        arch = "arm"
    else:
        error(f"Unsupported architecture: {machine}", exit_code=0)
        return False

    url = f"https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-{arch}"

    try:
        with tempfile.NamedTemporaryFile(delete=False) as tmp:
            log(f"Downloading from {url}...")
            urllib.request.urlretrieve(url, tmp.name)

            shutil.move(tmp.name, str(CLOUDFLARED_PATH))
            CLOUDFLARED_PATH.chmod(0o755)

        log("cloudflared installed successfully")
        return True
    except Exception as e:
        error(f"Failed to install cloudflared: {e}", exit_code=0)
        return False


def start_tunnel(port: int = GRPC_PORT) -> Optional[str]:
    """Start a Cloudflare quick tunnel and return the URL."""
    cloudflared = str(CLOUDFLARED_PATH) if CLOUDFLARED_PATH.exists() else "cloudflared"

    log(f"Starting Cloudflare tunnel for localhost:{port}...")

    # Start tunnel process
    process = subprocess.Popen(
        [
            cloudflared,
            "tunnel",
            "--url",
            f"http://localhost:{port}",
            "--protocol",
            "http2",
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
    )

    # Wait for tunnel URL in output
    url_pattern = re.compile(r"https://[a-zA-Z0-9-]+\.trycloudflare\.com")
    start_time = time.time()
    timeout = 30

    while time.time() - start_time < timeout:
        line = process.stdout.readline()
        if not line:
            if process.poll() is not None:
                error("Tunnel process exited unexpectedly", exit_code=0)
                return None
            continue

        match = url_pattern.search(line)
        if match:
            tunnel_url = match.group(0)

            # Save URL to file
            TUNNEL_URL_FILE.parent.mkdir(parents=True, exist_ok=True)
            TUNNEL_URL_FILE.write_text(tunnel_url)

            # Save PID
            pid_file = INSTALL_DIR / "tunnel.pid"
            pid_file.write_text(str(process.pid))

            return tunnel_url

    error("Timeout waiting for tunnel URL", exit_code=0)
    process.terminate()
    return None


def get_tunnel_url() -> Optional[str]:
    """Get the current tunnel URL if available."""
    if TUNNEL_URL_FILE.exists():
        url = TUNNEL_URL_FILE.read_text().strip()
        if url:
            return url
    return None


def stop_tunnel() -> None:
    """Stop the running tunnel."""
    pid_file = INSTALL_DIR / "tunnel.pid"
    if pid_file.exists():
        try:
            pid = int(pid_file.read_text().strip())
            os.kill(pid, 9)
            log("Tunnel stopped")
        except (ValueError, ProcessLookupError):
            pass
        pid_file.unlink(missing_ok=True)

    TUNNEL_URL_FILE.unlink(missing_ok=True)


# ============================================================================
# Systemd Service Management
# ============================================================================


def create_systemd_service(
    venv_path: Path, install_dir: Path, with_tunnel: bool = False
) -> bool:
    """Create systemd service file."""
    if not Path("/run/systemd/system").exists():
        warn("systemd not available, skipping service creation")
        return False

    python = get_venv_python(venv_path)
    if not python:
        return False

    # Main server service
    server_service = f"""[Unit]
Description=VDJ Stems GPU Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory={install_dir}
Environment="PATH={venv_path}/bin:/usr/local/bin:/usr/bin:/bin"
Environment="CUDA_VISIBLE_DEVICES=0"
ExecStart={venv_path}/bin/vdj-stems-server --host 0.0.0.0 --port {GRPC_PORT}
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""

    service_file = Path(f"/etc/systemd/system/{SERVICE_NAME}.service")

    try:
        service_file.write_text(server_service)
        subprocess.run(["systemctl", "daemon-reload"], check=True)
        subprocess.run(["systemctl", "enable", SERVICE_NAME], check=True)
        log(f"Created systemd service: {SERVICE_NAME}")
    except (PermissionError, subprocess.CalledProcessError) as e:
        error(f"Failed to create service: {e}", exit_code=0)
        return False

    # Tunnel service (if requested)
    if with_tunnel:
        cloudflared = (
            str(CLOUDFLARED_PATH)
            if CLOUDFLARED_PATH.exists()
            else "/usr/local/bin/cloudflared"
        )
        tunnel_service = f"""[Unit]
Description=VDJ Stems Cloudflare Tunnel
After=network.target {SERVICE_NAME}.service
Requires={SERVICE_NAME}.service

[Service]
Type=simple
User=root
ExecStart={cloudflared} tunnel --url http://localhost:{GRPC_PORT} --protocol http2
ExecStartPost=/bin/bash -c 'sleep 5 && journalctl -u {TUNNEL_SERVICE_NAME} -n 20 | grep -oP "https://[a-zA-Z0-9-]+\\.trycloudflare\\.com" | tail -1 > {TUNNEL_URL_FILE}'
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
"""
        tunnel_service_file = Path(f"/etc/systemd/system/{TUNNEL_SERVICE_NAME}.service")

        try:
            tunnel_service_file.write_text(tunnel_service)
            subprocess.run(["systemctl", "daemon-reload"], check=True)
            subprocess.run(["systemctl", "enable", TUNNEL_SERVICE_NAME], check=True)
            log(f"Created systemd service: {TUNNEL_SERVICE_NAME}")
        except (PermissionError, subprocess.CalledProcessError) as e:
            error(f"Failed to create tunnel service: {e}", exit_code=0)
            return False

    return True


def start_service(with_tunnel: bool = False) -> bool:
    """Start the systemd service."""
    try:
        subprocess.run(["systemctl", "start", SERVICE_NAME], check=True)
        log(f"Started {SERVICE_NAME}")

        if with_tunnel:
            subprocess.run(["systemctl", "start", TUNNEL_SERVICE_NAME], check=True)
            log(f"Started {TUNNEL_SERVICE_NAME}")

            # Wait for tunnel URL
            time.sleep(5)
            for _ in range(10):
                url = get_tunnel_url()
                if url:
                    return True
                time.sleep(1)

        return True
    except subprocess.CalledProcessError as e:
        error(f"Failed to start service: {e}", exit_code=0)
        return False


def stop_service() -> bool:
    """Stop the systemd services."""
    try:
        subprocess.run(["systemctl", "stop", TUNNEL_SERVICE_NAME], check=False)
        subprocess.run(["systemctl", "stop", SERVICE_NAME], check=True)
        log("Services stopped")
        return True
    except subprocess.CalledProcessError as e:
        error(f"Failed to stop service: {e}", exit_code=0)
        return False


def get_service_status() -> dict:
    """Get status of services."""
    status = {"server": "unknown", "tunnel": "unknown", "tunnel_url": None}

    try:
        result = subprocess.run(
            ["systemctl", "is-active", SERVICE_NAME], capture_output=True, text=True
        )
        status["server"] = result.stdout.strip()
    except FileNotFoundError:
        status["server"] = "systemd not available"

    try:
        result = subprocess.run(
            ["systemctl", "is-active", TUNNEL_SERVICE_NAME],
            capture_output=True,
            text=True,
        )
        status["tunnel"] = result.stdout.strip()
    except FileNotFoundError:
        pass

    status["tunnel_url"] = get_tunnel_url()

    return status


# ============================================================================
# Installation
# ============================================================================


def install(
    project_root: Path, sys_info: SystemInfo, with_tunnel: bool = False
) -> bool:
    """Install the server and dependencies."""
    server_dir = project_root / "server"
    proto_dir = project_root / "proto"
    venv_path = INSTALL_DIR / ".venv"

    # Create install directory
    INSTALL_DIR.mkdir(parents=True, exist_ok=True)

    # Copy server files (only if changed or missing)
    log("Syncing server files...")

    # Copy server directory
    dest_server = INSTALL_DIR
    for item in ["src", "pyproject.toml", "tests"]:
        src = server_dir / item
        dst = dest_server / item
        if src.exists():
            if src.is_dir():
                if dst.exists():
                    shutil.rmtree(dst)
                shutil.copytree(src, dst)
            else:
                shutil.copy2(src, dst)

    # Copy proto directory
    dest_proto = INSTALL_DIR / "proto"
    if dest_proto.exists():
        shutil.rmtree(dest_proto)
    shutil.copytree(proto_dir, dest_proto)

    # Check/create venv
    if is_venv_valid(venv_path):
        log("Using existing virtual environment")
    else:
        if venv_path.exists():
            warn("Existing venv is invalid, recreating...")
            shutil.rmtree(venv_path)
        if not create_venv(venv_path, use_uv=sys_info.has_uv):
            return False

    # Install/upgrade pip
    python = get_venv_python(venv_path)
    if not sys_info.has_uv:
        log("Upgrading pip...")
        subprocess.run(
            [str(python), "-m", "pip", "install", "-q", "--upgrade", "pip"], check=True
        )

    # Check if server package is installed
    if check_server_installed(venv_path):
        log("Server package already installed, checking for updates...")
    else:
        log("Installing server package...")

    # Install server package (editable for development)
    install_path = f"{INSTALL_DIR}[dev]"
    if not install_package(
        venv_path, install_path, use_uv=sys_info.has_uv, editable=True
    ):
        error("Failed to install server package", exit_code=0)
        return False

    # Install grpcio-tools if not present
    if not check_package_installed(venv_path, "grpcio-tools"):
        log("Installing grpcio-tools...")
        if not install_package(venv_path, "grpcio-tools", use_uv=sys_info.has_uv):
            error("Failed to install grpcio-tools", exit_code=0)
            return False

    # Generate proto files if needed
    if not check_proto_generated(INSTALL_DIR):
        if not generate_proto(INSTALL_DIR, venv_path):
            return False
    else:
        log("Proto files already generated")

    # Install cloudflared if tunnel requested
    if with_tunnel:
        if not sys_info.has_cloudflared:
            if not install_cloudflared():
                warn("Could not install cloudflared, tunnel will not be available")
                with_tunnel = False

    # Create systemd service
    if sys_info.has_systemd:
        if not create_systemd_service(venv_path, INSTALL_DIR, with_tunnel=with_tunnel):
            warn("Could not create systemd service")

    # Save config
    config = {
        "install_dir": str(INSTALL_DIR),
        "venv_path": str(venv_path),
        "port": GRPC_PORT,
        "with_tunnel": with_tunnel,
        "gpu_name": sys_info.gpu_name,
        "installed_at": time.strftime("%Y-%m-%d %H:%M:%S"),
    }
    CONFIG_FILE.write_text(json.dumps(config, indent=2))

    log("Installation complete!")
    return True


def uninstall() -> bool:
    """Remove everything."""
    log("Uninstalling...")

    # Stop services
    stop_service()
    stop_tunnel()

    for service in [SERVICE_NAME, TUNNEL_SERVICE_NAME]:
        service_file = Path(f"/etc/systemd/system/{service}.service")
        if service_file.exists():
            subprocess.run(["systemctl", "disable", service], check=False)
            service_file.unlink()

    subprocess.run(["systemctl", "daemon-reload"], check=False)

    if INSTALL_DIR.exists():
        shutil.rmtree(INSTALL_DIR)

    log("Uninstalled successfully")
    return True


# ============================================================================
# Main Commands
# ============================================================================


def cmd_install(args: argparse.Namespace) -> int:
    """Install command."""
    sys_info = detect_system()

    # Check prerequisites
    if sys_info.os_name != "Linux":
        error(f"This script is designed for Linux. Detected: {sys_info.os_name}")

    if sys_info.python_version < MIN_PYTHON_VERSION:
        error(
            f"Python {MIN_PYTHON_VERSION[0]}.{MIN_PYTHON_VERSION[1]}+ required. Found: {'.'.join(map(str, sys_info.python_version))}"
        )

    if not sys_info.is_root:
        error("Run as root: sudo python deploy.py install")

    # Find project
    project_root = find_project_root()
    if not project_root:
        error(
            "Cannot find project root. Run from project directory or server/ subdirectory."
        )

    log(f"Project root: {project_root}")

    # Show system info
    info(f"Python: {'.'.join(map(str, sys_info.python_version))}")
    info(f"Package manager: {'uv' if sys_info.has_uv else 'pip'}")
    if sys_info.has_nvidia_gpu:
        info(f"GPU: {sys_info.gpu_name} ({sys_info.gpu_memory_mb}MB)")
    else:
        warn("No NVIDIA GPU detected - will use CPU mode")

    # Install
    if not install(project_root, sys_info, with_tunnel=args.tunnel):
        return 1

    print()
    log("Next steps:")
    print(f"  sudo python {__file__} start" + (" --tunnel" if args.tunnel else ""))

    return 0


def cmd_start(args: argparse.Namespace) -> int:
    """Start command."""
    sys_info = detect_system()

    if not sys_info.is_root:
        error("Run as root: sudo python deploy.py start")

    if not INSTALL_DIR.exists():
        error(f"Server not installed. Run: sudo python {__file__} install")

    if sys_info.has_systemd:
        if not start_service(with_tunnel=args.tunnel):
            return 1
    else:
        # Foreground mode for non-systemd
        venv_path = INSTALL_DIR / ".venv"
        python = get_venv_python(venv_path)
        if not python:
            error("Virtual environment not found")

        # Start tunnel in background if requested
        tunnel_url = None
        if args.tunnel:
            if not sys_info.has_cloudflared:
                if not install_cloudflared():
                    error("Could not install cloudflared")
            tunnel_url = start_tunnel()
            if tunnel_url:
                print()
                print(f"{Colors.GREEN}{'=' * 60}{Colors.NC}")
                print(f"{Colors.GREEN}TUNNEL URL: {tunnel_url}{Colors.NC}")
                print(f"{Colors.GREEN}{'=' * 60}{Colors.NC}")
                print()

        log("Starting server in foreground (Ctrl+C to stop)...")
        os.chdir(INSTALL_DIR)
        os.execv(
            str(python),
            [
                str(python),
                "-m",
                "vdj_stems_server.main",
                "--host",
                "0.0.0.0",
                "--port",
                str(GRPC_PORT),
                "-v",
            ],
        )

    # Show tunnel URL
    if args.tunnel:
        time.sleep(2)
        url = get_tunnel_url()
        if url:
            print()
            print(f"{Colors.GREEN}{'=' * 60}{Colors.NC}")
            print(f"{Colors.GREEN}TUNNEL URL: {url}{Colors.NC}")
            print(f"{Colors.GREEN}{'=' * 60}{Colors.NC}")
            print()
            print("On Windows client, run:")
            print(f'  .\\scripts\\vdj-proxy-ctl.ps1 config -TunnelUrl "{url}"')
        else:
            warn("Tunnel URL not yet available. Check: journalctl -u vdj-stems-tunnel")
    else:
        ip = (
            subprocess.run(
                ["hostname", "-I"], capture_output=True, text=True
            ).stdout.split()[0]
            if subprocess.run(
                ["hostname", "-I"], capture_output=True, text=True
            ).returncode
            == 0
            else "unknown"
        )
        print()
        log(f"Server running at {ip}:{GRPC_PORT}")

    return 0


def cmd_stop(args: argparse.Namespace) -> int:
    """Stop command."""
    sys_info = detect_system()

    if not sys_info.is_root:
        error("Run as root: sudo python deploy.py stop")

    stop_tunnel()

    if sys_info.has_systemd:
        if not stop_service():
            return 1

    return 0


def cmd_status(args: argparse.Namespace) -> int:
    """Status command."""
    print()
    print("=== Service Status ===")

    status = get_service_status()
    print(f"Server: {status['server']}")
    print(f"Tunnel: {status['tunnel']}")
    if status["tunnel_url"]:
        print(f"Tunnel URL: {status['tunnel_url']}")

    print()
    print("=== GPU Status ===")
    sys_info = detect_system()
    if sys_info.has_nvidia_gpu:
        print(f"GPU: {sys_info.gpu_name} ({sys_info.gpu_memory_mb}MB)")
        subprocess.run(
            [
                "nvidia-smi",
                "--query-gpu=utilization.gpu,memory.used,memory.total",
                "--format=csv,noheader",
            ]
        )
    else:
        print("No NVIDIA GPU detected")

    print()
    print("=== Network ===")
    try:
        ip = subprocess.run(
            ["hostname", "-I"], capture_output=True, text=True
        ).stdout.split()[0]
        print(f"Server IP: {ip}")
    except (subprocess.CalledProcessError, IndexError):
        print("Server IP: unknown")
    print(f"Port: {GRPC_PORT}")

    # Check if port is listening
    result = subprocess.run(["ss", "-tlnp"], capture_output=True, text=True)
    if str(GRPC_PORT) in result.stdout:
        print(f"Port {GRPC_PORT}: LISTENING")
    else:
        print(f"Port {GRPC_PORT}: NOT LISTENING")

    return 0


def cmd_tunnel(args: argparse.Namespace) -> int:
    """Start tunnel only."""
    sys_info = detect_system()

    if not sys_info.has_cloudflared:
        if not install_cloudflared():
            error("Could not install cloudflared")

    url = start_tunnel()
    if url:
        print()
        print(f"{Colors.GREEN}{'=' * 60}{Colors.NC}")
        print(f"{Colors.GREEN}TUNNEL URL: {url}{Colors.NC}")
        print(f"{Colors.GREEN}{'=' * 60}{Colors.NC}")
        print()
        print("On Windows client, run:")
        print(f'  .\\scripts\\vdj-proxy-ctl.ps1 config -TunnelUrl "{url}"')
        print()
        print("Press Ctrl+C to stop tunnel...")

        try:
            while True:
                time.sleep(1)
        except KeyboardInterrupt:
            stop_tunnel()

    return 0


def cmd_uninstall(args: argparse.Namespace) -> int:
    """Uninstall command."""
    sys_info = detect_system()

    if not sys_info.is_root:
        error("Run as root: sudo python deploy.py uninstall")

    if not uninstall():
        return 1

    return 0


def cmd_logs(args: argparse.Namespace) -> int:
    """Show logs."""
    service = TUNNEL_SERVICE_NAME if args.tunnel else SERVICE_NAME
    subprocess.run(["journalctl", "-u", service, "-f", "--no-hostname"])
    return 0


# ============================================================================
# Entry Point
# ============================================================================


def main() -> int:
    parser = argparse.ArgumentParser(
        description="VDJ Stems Server Deployment",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  sudo python deploy.py install --tunnel   # Install with Cloudflare tunnel
  sudo python deploy.py start --tunnel     # Start server with tunnel
  sudo python deploy.py status             # Show status and tunnel URL
  python deploy.py tunnel                  # Start tunnel only (for testing)
        """,
    )

    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Install
    install_parser = subparsers.add_parser(
        "install", help="Install server and dependencies"
    )
    install_parser.add_argument(
        "--tunnel", action="store_true", help="Enable Cloudflare tunnel"
    )
    install_parser.set_defaults(func=cmd_install)

    # Start
    start_parser = subparsers.add_parser("start", help="Start the server")
    start_parser.add_argument(
        "--tunnel", action="store_true", help="Start with Cloudflare tunnel"
    )
    start_parser.set_defaults(func=cmd_start)

    # Stop
    stop_parser = subparsers.add_parser("stop", help="Stop the server")
    stop_parser.set_defaults(func=cmd_stop)

    # Status
    status_parser = subparsers.add_parser("status", help="Show status")
    status_parser.set_defaults(func=cmd_status)

    # Tunnel
    tunnel_parser = subparsers.add_parser("tunnel", help="Start tunnel only")
    tunnel_parser.set_defaults(func=cmd_tunnel)

    # Logs
    logs_parser = subparsers.add_parser("logs", help="Show logs")
    logs_parser.add_argument("--tunnel", action="store_true", help="Show tunnel logs")
    logs_parser.set_defaults(func=cmd_logs)

    # Uninstall
    uninstall_parser = subparsers.add_parser("uninstall", help="Remove everything")
    uninstall_parser.set_defaults(func=cmd_uninstall)

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return 0

    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
