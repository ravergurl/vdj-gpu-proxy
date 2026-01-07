#!/bin/bash
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
ROOT_DIR="$(dirname "$SCRIPT_DIR")"

echo "Installing VDJ Stems Server..."

python3 --version || { echo "Python 3 required"; exit 1; }

if command -v nvidia-smi &> /dev/null; then
    echo "CUDA GPU detected:"
    nvidia-smi --query-gpu=name,memory.total --format=csv
else
    echo "Warning: No NVIDIA GPU detected. Server will use CPU."
fi

cd "$ROOT_DIR/server"
if command -v uv &> /dev/null; then
    echo "Using uv for virtual environment..."
    uv venv
    source .venv/bin/activate
else
    echo "Using venv for virtual environment..."
    python3 -m venv venv
    source venv/bin/activate
fi

echo "Installing dependencies..."
pip install --upgrade pip
if command -v uv &> /dev/null; then
    uv pip install -e .
else
    pip install -e .
fi

echo "Generating proto files..."
cd "$ROOT_DIR"
if command -v uv &> /dev/null; then
    uv pip install grpcio-tools
else
    pip install grpcio-tools
fi

if [ -f "scripts/generate_proto.py" ]; then
    python3 scripts/generate_proto.py
else
    python3 -m grpc_tools.protoc -I./proto --python_out=./server/src/vdj_stems_server --grpc_python_out=./server/src/vdj_stems_server ./proto/stems.proto
fi

echo ""
echo "Installation complete!"
echo ""
echo "To start the server:"
echo "  cd $ROOT_DIR/server"
if [ -d ".venv" ]; then
    echo "  source .venv/bin/activate"
else
    echo "  source venv/bin/activate"
fi
echo "  vdj-stems-server --host 0.0.0.0 --port 50051"
