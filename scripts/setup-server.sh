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
echo "  (uv for maximum speed)"
echo -e "========================================${NC}"
echo ""

# Check Python version
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

# Check GPU
if command -v nvidia-smi &> /dev/null; then
    log_success "NVIDIA GPU detected:"
    nvidia-smi --query-gpu=name,memory.total,driver_version --format=csv,noheader | head -1
else
    log_warn "No NVIDIA GPU detected - will use CPU (slow)"
fi

# Install uv if not present (10-100x faster than pip)
if ! command -v uv &> /dev/null; then
    log_status "Installing uv (fast Python package manager)..."
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.cargo/bin:$PATH"
fi

if command -v uv &> /dev/null; then
    log_success "uv $(uv --version)"
else
    log_error "Failed to install uv"
    exit 1
fi

# Setup Python environment
log_status "Creating virtual environment with uv..."
cd "$ROOT_DIR/server"

uv venv .venv
source .venv/bin/activate

# Install dependencies (blazing fast with uv)
log_status "Installing Python dependencies..."
uv pip install -e ".[dev]"

# Generate proto files
log_status "Generating proto files..."
cd "$ROOT_DIR"
uv pip install grpcio-tools
python3 scripts/generate_proto.py

# Run tests
log_status "Running tests..."
cd "$ROOT_DIR/server"
python -m pytest tests/ -v --tb=short || log_warn "Some tests failed"

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
