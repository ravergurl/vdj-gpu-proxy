#!/usr/bin/env python3
"""Test HTTP inference endpoint directly."""

import base64
import json
import numpy as np
import requests

URL = "https://vdj-gpu-direct.ai-smith.net"


def main():
    # Test health
    print("Testing health endpoint...")
    r = requests.get(f"{URL}/health", timeout=10)
    print(f"  Status: {r.status_code}")
    print(f"  Response: {r.text}")

    # Test info
    print("\nTesting info endpoint...")
    r = requests.get(f"{URL}/info", timeout=10)
    print(f"  Status: {r.status_code}")
    print(f"  Response: {r.text}")

    # Test inference with small fake audio
    print("\nTesting inference endpoint...")

    # Create fake audio tensor (1 second stereo @ 44100)
    # Shape: [2, 44100] dtype: float32
    audio = np.random.randn(2, 44100).astype(np.float32) * 0.5
    audio_bytes = audio.tobytes()
    audio_b64 = base64.b64encode(audio_bytes).decode()

    payload = {
        "session_id": 1,
        "input_names": ["audio"],
        "inputs": [
            {
                "shape": [2, 44100],
                "dtype": 1,  # float32 = 1 in ONNX
                "data": audio_b64,
            }
        ],
        "output_names": ["drums", "bass", "other", "vocals"],
    }

    print(f"  Sending {len(audio_bytes)} bytes of audio...")
    try:
        r = requests.post(f"{URL}/inference", json=payload, timeout=120)
        print(f"  Status: {r.status_code}")
        if r.status_code == 200:
            result = r.json()
            print(f"  Got {len(result.get('outputs', []))} outputs")
            for i, out in enumerate(result.get("outputs", [])):
                shape = out.get("shape", [])
                data_len = len(out.get("data", ""))
                print(f"    Output {i}: shape={shape}, data_len={data_len}")
        else:
            print(f"  Error: {r.text[:500]}")
    except Exception as e:
        print(f"  Exception: {e}")


if __name__ == "__main__":
    main()
