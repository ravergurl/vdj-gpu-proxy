#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SERVICE_NAME="vdj-stems-server"
INSTALL_DIR="/opt/vdj-stems-server"
VENV_DIR="$INSTALL_DIR/.venv"

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log() { echo -e "${GREEN}[+]${NC} $1"; }
warn() { echo -e "${YELLOW}[!]${NC} $1"; }
error() { echo -e "${RED}[x]${NC} $1"; exit 1; }

check_root() {
    if [[ $EUID -ne 0 ]]; then
        error "Run as root: sudo $0 $*"
    fi
}

check_gpu() {
    if command -v nvidia-smi &> /dev/null; then
        log "NVIDIA GPU detected:"
        nvidia-smi --query-gpu=name,memory.total --format=csv,noheader | head -1
    else
        warn "No NVIDIA GPU detected - will use CPU mode"
    fi
}

install_server() {
    log "Installing VDJ Stems Server to $INSTALL_DIR"
    
    mkdir -p "$INSTALL_DIR"
    cp -r "$PROJECT_DIR/server/"* "$INSTALL_DIR/"
    cp -r "$PROJECT_DIR/proto" "$INSTALL_DIR/"
    cp -r "$PROJECT_DIR/scripts/generate_proto.py" "$INSTALL_DIR/"
    
    log "Creating virtual environment..."
    python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
    
    log "Installing dependencies..."
    pip install --upgrade pip
    pip install -e "$INSTALL_DIR[dev]"
    pip install grpcio-tools
    
    log "Generating proto files..."
    cd "$INSTALL_DIR"
    python generate_proto.py
    
    deactivate
    log "Server installed successfully"
}

create_service() {
    log "Creating systemd service..."
    
    cat > /etc/systemd/system/${SERVICE_NAME}.service << EOF
[Unit]
Description=VDJ Stems GPU Server
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=$INSTALL_DIR
Environment="PATH=$VENV_DIR/bin:/usr/local/bin:/usr/bin:/bin"
Environment="CUDA_VISIBLE_DEVICES=0"
ExecStart=$VENV_DIR/bin/vdj-stems-server --host 0.0.0.0 --port 50051
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable ${SERVICE_NAME}
    log "Service created and enabled"
}

start_server() {
    log "Starting ${SERVICE_NAME}..."
    systemctl start ${SERVICE_NAME}
    sleep 2
    if systemctl is-active --quiet ${SERVICE_NAME}; then
        log "Server started successfully"
        systemctl status ${SERVICE_NAME} --no-pager
    else
        error "Failed to start server. Check: journalctl -u ${SERVICE_NAME} -f"
    fi
}

stop_server() {
    log "Stopping ${SERVICE_NAME}..."
    systemctl stop ${SERVICE_NAME} || true
    log "Server stopped"
}

show_status() {
    echo ""
    echo "=== Service Status ==="
    systemctl status ${SERVICE_NAME} --no-pager || true
    echo ""
    echo "=== GPU Status ==="
    nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader 2>/dev/null || echo "No GPU"
    echo ""
    echo "=== Connection Test ==="
    if command -v grpcurl &> /dev/null; then
        grpcurl -plaintext localhost:50051 list 2>/dev/null || echo "Server not responding"
    else
        echo "Install grpcurl for connection test"
    fi
}

show_logs() {
    journalctl -u ${SERVICE_NAME} -f
}

uninstall() {
    log "Uninstalling ${SERVICE_NAME}..."
    systemctl stop ${SERVICE_NAME} 2>/dev/null || true
    systemctl disable ${SERVICE_NAME} 2>/dev/null || true
    rm -f /etc/systemd/system/${SERVICE_NAME}.service
    systemctl daemon-reload
    rm -rf "$INSTALL_DIR"
    log "Uninstalled successfully"
}

show_help() {
    echo "VDJ Stems Server Deploy Script"
    echo ""
    echo "Usage: sudo $0 <command>"
    echo ""
    echo "Commands:"
    echo "  install   - Install server and create systemd service"
    echo "  start     - Start the server"
    echo "  stop      - Stop the server"
    echo "  restart   - Restart the server"
    echo "  status    - Show server status"
    echo "  logs      - Follow server logs"
    echo "  uninstall - Remove server and service"
    echo ""
    echo "Quick start:"
    echo "  sudo $0 install && sudo $0 start"
}

case "${1:-}" in
    install)
        check_root
        check_gpu
        install_server
        create_service
        log "Installation complete! Run: sudo $0 start"
        ;;
    start)
        check_root
        start_server
        ;;
    stop)
        check_root
        stop_server
        ;;
    restart)
        check_root
        stop_server
        start_server
        ;;
    status)
        show_status
        ;;
    logs)
        show_logs
        ;;
    uninstall)
        check_root
        uninstall
        ;;
    *)
        show_help
        ;;
esac
