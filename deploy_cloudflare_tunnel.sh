#!/bin/bash
# Deploy Cloudflare Tunnel Configuration for HTTP Binary Streaming
# Run this on the remote GPU server after updating the server code

set -e

echo "=== VDJ GPU Proxy - Cloudflare Tunnel Deployment ==="
echo

# Check if cloudflared is installed
if ! command -v cloudflared &> /dev/null; then
    echo "Installing cloudflared..."
    curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-amd64 -o /usr/local/bin/cloudflared
    chmod +x /usr/local/bin/cloudflared
    echo "✓ cloudflared installed"
fi

# Create .cloudflared directory
mkdir -p ~/.cloudflared

# Create credentials file
echo "Creating credentials file..."
cat > ~/.cloudflared/831e1b5b-33d5-4ef3-a4c8-b4e4eccda4d8.json <<'EOF'
{
  "AccountTag": "4c2932bc3381be38d5266241b16be092",
  "TunnelID": "831e1b5b-33d5-4ef3-a4c8-b4e4eccda4d8",
  "TunnelName": "vdj-local",
  "TunnelSecret": "BePxHzSEDqOjsqcRzA/lss46X8ERExAYA9z1pKHc+Lk="
}
EOF
echo "✓ Credentials file created"

# Create tunnel config
echo "Creating tunnel configuration..."
cat > ~/.cloudflared/config.yml <<'EOF'
tunnel: 831e1b5b-33d5-4ef3-a4c8-b4e4eccda4d8
credentials-file: /root/.cloudflared/831e1b5b-33d5-4ef3-a4c8-b4e4eccda4d8.json

# HTTP Binary Streaming Configuration
# Routes all traffic to port 8081 where HTTP streaming server runs
ingress:
  - hostname: vdj-gpu-direct.ai-smith.net
    service: http://localhost:8081
  - service: http_status:404
EOF
echo "✓ Config file created"

# Stop existing cloudflared if running
echo "Stopping existing cloudflared..."
pkill -f cloudflared || true
sleep 2

# Start cloudflared tunnel
echo "Starting cloudflared tunnel..."
nohup cloudflared tunnel --config ~/.cloudflared/config.yml run > ~/.cloudflared/tunnel.log 2>&1 &

sleep 3

# Check if tunnel is running
if pgrep -f cloudflared > /dev/null; then
    echo "✓ Cloudflared tunnel started successfully"
    echo
    echo "Tunnel Details:"
    echo "  Hostname: vdj-gpu-direct.ai-smith.net"
    echo "  Target:   http://localhost:8081"
    echo "  Log:      ~/.cloudflared/tunnel.log"
    echo
    echo "To monitor: tail -f ~/.cloudflared/tunnel.log"
else
    echo "✗ Failed to start cloudflared"
    echo "Check logs: cat ~/.cloudflared/tunnel.log"
    exit 1
fi
