#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

RED='\033[0;31m'
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
NC='\033[0m'

log_status() { echo -e "${CYAN}[*]${NC} $1"; }
log_success() { echo -e "${GREEN}[+]${NC} $1"; }
log_warn() { echo -e "${YELLOW}[!]${NC} $1"; }
log_error() { echo -e "${RED}[-]${NC} $1"; }

echo ""
echo -e "${CYAN}========================================"
echo "  VDJ-GPU-Proxy Server Setup"
echo -e "========================================${NC}"
echo ""

if ! command -v python3 &> /dev/null; then
    log_error "Python 3.10+ is required"
    exit 1
fi

PYTHON_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
PYTHON_MAJOR=$(echo $PYTHON_VERSION | cut -d. -f1)
PYTHON_MINOR=$(echo $PYTHON_VERSION | cut -d. -f2)

if [[ $PYTHON_MAJOR -lt 3 ]] || [[ $PYTHON_MAJOR -eq 3 && $PYTHON_MINOR -lt 10 ]]; then
    log_error "Python 3.10+ required (found $PYTHON_VERSION)"
    exit 1
fi
log_success "Python $PYTHON_VERSION found"

if command -v nvidia-smi &> /dev/null; then
    log_success "NVIDIA GPU detected:"
    nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader | head -1
else
    log_warn "No NVIDIA GPU detected - will use CPU (slow)"
fi

log_status "Creating virtual environment..."
cd "$ROOT_DIR/server"

VENV_DIR=".venv"
if command -v uv &> /dev/null; then
    log_status "Using uv for fast package management..."
    uv venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
    uv pip install -e ".[dev]"
else
    python3 -m venv "$VENV_DIR"
    source "$VENV_DIR/bin/activate"
    pip install --upgrade pip
    pip install -e ".[dev]"
fi

log_status "Generating proto files..."
cd "$ROOT_DIR"
pip install grpcio-tools
python3 scripts/generate_proto.py

log_status "Running tests..."
cd "$ROOT_DIR/server"
pytest tests/ -v --tb=short || log_warn "Some tests failed (may be expected without GPU)"

echo ""
echo -e "${GREEN}========================================"
echo "  Server Setup Complete!"
echo -e "========================================${NC}"
echo ""
echo "To start the server:"
echo "  cd $ROOT_DIR/server"
echo "  source .venv/bin/activate"
echo "  vdj-stems-server --host 0.0.0.0 --port 50051"
echo ""
echo "To run with verbose logging:"
echo "  vdj-stems-server -v --host 0.0.0.0 --port 50051"
echo ""
