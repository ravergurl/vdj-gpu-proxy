#!/data/data/com.termux/files/usr/bin/bash
#
# VDJ Stems Server - Termux Setup Script
# Run this inside Termux on your Pixel 8 Pro
#

set -e

echo "============================================"
echo "VDJ Stems Server - Termux Setup"
echo "============================================"
echo ""

# Update packages
echo "[1/6] Updating Termux packages..."
pkg update -y
pkg upgrade -y

# Install Python and dependencies
echo "[2/6] Installing Python and build tools..."
pkg install -y python python-pip git cmake ninja patchelf

# Install numpy (from Termux repo - faster than pip)
echo "[3/6] Installing numpy..."
pkg install -y python-numpy

# Create project directory
echo "[4/6] Setting up project directory..."
mkdir -p ~/vdj-stems
cd ~/vdj-stems

# Install PyTorch for ARM64
echo "[5/6] Installing PyTorch..."
echo "This may take a while..."

# Use pip with specific versions known to work on ARM64
pip install --upgrade pip wheel setuptools

# PyTorch for Android/ARM - use CPU version
# The official wheels should work on aarch64
pip install torch torchaudio --index-url https://download.pytorch.org/whl/cpu

# Install Demucs
echo "[6/6] Installing Demucs..."
pip install demucs

echo ""
echo "============================================"
echo "Setup complete!"
echo "============================================"
echo ""
echo "To start the server:"
echo "  cd ~/vdj-stems"
echo "  python termux_server.py"
echo ""
echo "The server will listen on port 8081"
echo ""
echo "On your Windows PC, run:"
echo "  adb forward tcp:8081 tcp:8081"
echo ""
echo "Then configure VDJ proxy to use:"
echo "  Server: 127.0.0.1"
echo "  Port: 8081"
echo ""
