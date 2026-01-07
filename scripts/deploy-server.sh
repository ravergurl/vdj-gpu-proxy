#!/bin/bash
set -e

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

find_project_root() {
    local dir="$1"
    while [[ "$dir" != "/" ]]; do
        if [[ -f "$dir/server/pyproject.toml" && -d "$dir/proto" ]]; then
            echo "$dir"
            return 0
        fi
        dir="$(dirname "$dir")"
    done
    return 1
}

detect_project() {
    local script_dir="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
    local cwd="$(pwd)"
    
    if PROJECT_DIR=$(find_project_root "$script_dir"); then
        log "Found project at: $PROJECT_DIR"
    elif PROJECT_DIR=$(find_project_root "$cwd"); then
        log "Found project at: $PROJECT_DIR"
    elif [[ -f "./pyproject.toml" && -d "../proto" ]]; then
        PROJECT_DIR="$(dirname "$(pwd)")"
        log "Found project at: $PROJECT_DIR (running from server/)"
    elif [[ -f "./server/pyproject.toml" && -d "./proto" ]]; then
        PROJECT_DIR="$(pwd)"
        log "Found project at: $PROJECT_DIR"
    else
        error "Cannot find project. Run from project root or server/ directory."
    fi
    
    SERVER_DIR="$PROJECT_DIR/server"
    PROTO_DIR="$PROJECT_DIR/proto"
    
    [[ -f "$SERVER_DIR/pyproject.toml" ]] || error "Missing: $SERVER_DIR/pyproject.toml"
    [[ -d "$PROTO_DIR" ]] || error "Missing: $PROTO_DIR"
}

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

setup_venv() {
    log "Setting up Python environment..."
    
    if command -v uv &> /dev/null; then
        log "Using uv (fast mode)"
        uv venv "$VENV_DIR"
        source "$VENV_DIR/bin/activate"
        uv pip install --upgrade pip
        uv pip install -e "$INSTALL_DIR[dev]"
        uv pip install grpcio-tools
    else
        log "Using pip (install 'uv' for faster installs)"
        python3 -m venv "$VENV_DIR"
        source "$VENV_DIR/bin/activate"
        pip install --upgrade pip -q
        pip install -e "$INSTALL_DIR[dev]"
        pip install grpcio-tools
    fi
}

generate_protos() {
    log "Generating proto files..."
    source "$VENV_DIR/bin/activate"
    
    local proto_file="$INSTALL_DIR/proto/stems.proto"
    local out_dir="$INSTALL_DIR/src/vdj_stems_server"
    
    python -m grpc_tools.protoc \
        -I"$INSTALL_DIR/proto" \
        --python_out="$out_dir" \
        --grpc_python_out="$out_dir" \
        "$proto_file"
    
    sed -i 's/^import stems_pb2/from . import stems_pb2/' "$out_dir/stems_pb2_grpc.py" 2>/dev/null || \
    sed -i '' 's/^import stems_pb2/from . import stems_pb2/' "$out_dir/stems_pb2_grpc.py"
    
    log "Proto files generated"
}

install_server() {
    detect_project
    
    log "Installing VDJ Stems Server to $INSTALL_DIR"
    
    rm -rf "$INSTALL_DIR"
    mkdir -p "$INSTALL_DIR"
    
    cp -r "$SERVER_DIR/"* "$INSTALL_DIR/"
    cp -r "$PROTO_DIR" "$INSTALL_DIR/"
    
    setup_venv
    generate_protos
    
    deactivate 2>/dev/null || true
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
StandardOutput=journal
StandardError=journal

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
        log "Server running on 0.0.0.0:50051"
        local ip=$(hostname -I | awk '{print $1}')
        log "Connect from Windows: $ip:50051"
    else
        error "Failed to start. Check: journalctl -u ${SERVICE_NAME} -n 50"
    fi
}

stop_server() {
    log "Stopping ${SERVICE_NAME}..."
    systemctl stop ${SERVICE_NAME} 2>/dev/null || true
    log "Server stopped"
}

show_status() {
    echo ""
    echo "=== Service Status ==="
    systemctl status ${SERVICE_NAME} --no-pager -l 2>/dev/null || echo "Service not installed"
    echo ""
    echo "=== GPU Status ==="
    nvidia-smi --query-gpu=name,memory.used,memory.total,utilization.gpu --format=csv,noheader 2>/dev/null || echo "No GPU detected"
    echo ""
    echo "=== Network ==="
    local ip=$(hostname -I 2>/dev/null | awk '{print $1}')
    echo "Server IP: ${ip:-unknown}"
    echo "Port: 50051"
    ss -tlnp 2>/dev/null | grep 50051 || netstat -tlnp 2>/dev/null | grep 50051 || echo "Port 50051 not listening"
}

show_logs() {
    journalctl -u ${SERVICE_NAME} -f --no-hostname
}

uninstall() {
    log "Uninstalling ${SERVICE_NAME}..."
    systemctl stop ${SERVICE_NAME} 2>/dev/null || true
    systemctl disable ${SERVICE_NAME} 2>/dev/null || true
    rm -f /etc/systemd/system/${SERVICE_NAME}.service
    systemctl daemon-reload
    rm -rf "$INSTALL_DIR"
    log "Uninstalled"
}

run_foreground() {
    detect_project
    log "Running server in foreground (Ctrl+C to stop)..."
    
    if [[ ! -d "$INSTALL_DIR/.venv" ]]; then
        error "Server not installed. Run: sudo $0 install"
    fi
    
    source "$INSTALL_DIR/.venv/bin/activate"
    exec vdj-stems-server --host 0.0.0.0 --port 50051 -v
}

show_help() {
    echo "VDJ Stems Server Deploy Script"
    echo ""
    echo "Usage: sudo $0 <command>"
    echo ""
    echo "Commands:"
    echo "  install   - Install server and create systemd service"
    echo "  start     - Start the server daemon"
    echo "  stop      - Stop the server"
    echo "  restart   - Restart the server"
    echo "  status    - Show server and GPU status"
    echo "  logs      - Follow server logs"
    echo "  run       - Run server in foreground (for testing)"
    echo "  uninstall - Remove server completely"
    echo ""
    echo "Quick start:"
    echo "  sudo $0 install"
    echo "  sudo $0 start"
}

case "${1:-}" in
    install)
        check_root
        check_gpu
        install_server
        create_service
        echo ""
        log "Installation complete!"
        log "Start with: sudo $0 start"
        log "Or test with: sudo $0 run"
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
    run)
        run_foreground
        ;;
    uninstall)
        check_root
        uninstall
        ;;
    *)
        show_help
        ;;
esac
