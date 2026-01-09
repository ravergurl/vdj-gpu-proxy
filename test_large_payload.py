"""Test if server accepts 28MB inference request"""
import requests
import base64
import json
import numpy as np
import time

# Server URL
SERVER_URL = "https://vdj-gpu-direct.ai-smith.net"

print("Creating test tensors matching VDJ's inference request...")

# Create tensors matching the debug output:
# Input[0]: shape=[1,2,531456] dtype=1 (float32) dataLen=4251648
# Input[1]: shape=[1,4,2048,519] dtype=1 (float32) dataLen=17006592

input0_shape = [1, 2, 531456]
input0_data = np.random.randn(*input0_shape).astype(np.float32)
input0_bytes = input0_data.tobytes()
input0_b64 = base64.b64encode(input0_bytes).decode('utf-8')

input1_shape = [1, 4, 2048, 519]
input1_data = np.random.randn(*input1_shape).astype(np.float32)
input1_bytes = input1_data.tobytes()
input1_b64 = base64.b64encode(input1_bytes).decode('utf-8')

# Build JSON request
request_data = {
    "session_id": 1,
    "inputs": [
        {
            "name": "input",
            "shape": input0_shape,
            "dtype": 1,  # ONNX_TENSOR_ELEMENT_DATA_TYPE_FLOAT
            "data": input0_b64
        },
        {
            "name": "input2",
            "shape": input1_shape,
            "dtype": 1,
            "data": input1_b64
        }
    ],
    "outputs": ["output", "output2"]
}

json_str = json.dumps(request_data)
json_bytes = json_str.encode('utf-8')
payload_size_mb = len(json_bytes) / (1024 * 1024)

print(f"Input 0: shape={input0_shape}, size={len(input0_bytes)} bytes, base64={len(input0_b64)} chars")
print(f"Input 1: shape={input1_shape}, size={len(input1_bytes)} bytes, base64={len(input1_b64)} chars")
print(f"Total JSON payload: {len(json_bytes)} bytes ({payload_size_mb:.2f} MB)")
print()

# Test health first
print("Testing /health endpoint...")
try:
    resp = requests.get(f"{SERVER_URL}/health", timeout=10)
    print(f"  Status: {resp.status_code}")
    print(f"  Response: {resp.text}")
except Exception as e:
    print(f"  ERROR: {e}")
    exit(1)

print()

# Test inference with large payload
print(f"Sending {payload_size_mb:.2f} MB POST to /inference...")
print("This may take 30-60 seconds...")
start_time = time.time()

try:
    resp = requests.post(
        f"{SERVER_URL}/inference",
        json=request_data,
        timeout=120,  # 2 minute timeout
        headers={"Content-Type": "application/json"}
    )
    elapsed = time.time() - start_time

    print(f"  Status: {resp.status_code}")
    print(f"  Time: {elapsed:.2f} seconds")

    if resp.status_code == 200:
        print("  SUCCESS: Server accepted 28MB payload")
        result = resp.json()
        print(f"  Outputs: {len(result.get('outputs', []))} tensors")
    else:
        print(f"  FAILED: {resp.status_code}")
        print(f"  Response: {resp.text[:500]}")

except requests.exceptions.Timeout:
    elapsed = time.time() - start_time
    print(f"  TIMEOUT after {elapsed:.2f} seconds")
    print("  Server did not respond within 2 minutes")

except requests.exceptions.ConnectionError as e:
    elapsed = time.time() - start_time
    print(f"  CONNECTION ERROR after {elapsed:.2f} seconds")
    print(f"  {e}")

except Exception as e:
    elapsed = time.time() - start_time
    print(f"  ERROR after {elapsed:.2f} seconds")
    print(f"  {type(e).__name__}: {e}")
