#!/usr/bin/env python3
"""
Test script to verify phone inference server is working.
Run this on Windows after setting up ADB port forwarding.
"""

import struct
import time
import numpy as np
import requests

SERVER_URL = "http://127.0.0.1:8081"


def write_uint32(value: int) -> bytes:
    return struct.pack("<I", value)


def write_string(s: str) -> bytes:
    encoded = s.encode("utf-8")
    return write_uint32(len(encoded)) + encoded


def write_shape(shape: tuple) -> bytes:
    result = write_uint32(len(shape))
    for dim in shape:
        result += struct.pack("<q", dim)
    return result


def read_uint32(data: bytes, offset: int) -> tuple:
    value = struct.unpack("<I", data[offset:offset+4])[0]
    return value, offset + 4


def read_string(data: bytes, offset: int) -> tuple:
    length, offset = read_uint32(data, offset)
    string = data[offset:offset+length].decode("utf-8")
    return string, offset + length


def read_shape(data: bytes, offset: int) -> tuple:
    ndim, offset = read_uint32(data, offset)
    shape = []
    for _ in range(ndim):
        dim = struct.unpack("<q", data[offset:offset+8])[0]
        shape.append(dim)
        offset += 8
    return tuple(shape), offset


def create_test_audio(duration_sec: float = 5.0, sample_rate: int = 44100) -> np.ndarray:
    """Create test audio: stereo sine wave at 440Hz."""
    t = np.linspace(0, duration_sec, int(sample_rate * duration_sec), dtype=np.float32)
    # Mix of frequencies to simulate music
    audio = (
        0.3 * np.sin(2 * np.pi * 440 * t) +   # A4
        0.2 * np.sin(2 * np.pi * 554 * t) +   # C#5
        0.2 * np.sin(2 * np.pi * 659 * t) +   # E5
        0.1 * np.sin(2 * np.pi * 110 * t)     # A2 (bass)
    )
    # Stereo
    stereo = np.stack([audio, audio])
    return stereo.astype(np.float32)


def build_request(audio: np.ndarray, session_id: int = 1) -> bytes:
    """Build binary inference request."""
    request = write_uint32(session_id)  # session_id
    request += write_uint32(1)  # num_inputs

    # Input tensor
    request += write_string("audio")  # name
    request += write_shape(audio.shape)  # shape
    request += write_uint32(1)  # dtype = FLOAT32
    audio_bytes = audio.tobytes()
    request += write_uint32(len(audio_bytes))  # data_len
    request += audio_bytes  # data

    # Output names
    output_names = ["drums", "bass", "other", "vocals"]
    request += write_uint32(len(output_names))
    for name in output_names:
        request += write_string(name)

    return request


def parse_response(data: bytes) -> dict:
    """Parse binary inference response."""
    offset = 0
    session_id, offset = read_uint32(data, offset)
    status, offset = read_uint32(data, offset)
    error_len, offset = read_uint32(data, offset)

    if error_len > 0:
        error_msg = data[offset:offset+error_len].decode("utf-8")
        offset += error_len
        return {"error": error_msg, "status": status}

    num_outputs, offset = read_uint32(data, offset)

    stems = {}
    for _ in range(num_outputs):
        name, offset = read_string(data, offset)
        shape, offset = read_shape(data, offset)
        dtype, offset = read_uint32(data, offset)
        data_len, offset = read_uint32(data, offset)
        tensor_data = data[offset:offset+data_len]
        offset += data_len

        stems[name] = {
            "shape": shape,
            "dtype": dtype,
            "size_mb": len(tensor_data) / (1024 * 1024)
        }

    return {"session_id": session_id, "status": status, "stems": stems}


def main():
    # Test health endpoint
    print("Testing health endpoint...")
    try:
        r = requests.get(f"{SERVER_URL}/health", timeout=5)
        print(f"  Health: {r.json()}")
    except Exception as e:
        print(f"  Failed: {e}")
        print("\nMake sure:")
        print("  1. Termux server is running")
        print("  2. ADB port forwarding is active: adb forward tcp:8081 tcp:8081")
        return

    # Create test audio
    duration = 5.0
    print(f"\nCreating {duration}s test audio...")
    audio = create_test_audio(duration_sec=duration)
    print(f"  Shape: {audio.shape}")
    print(f"  Size: {audio.nbytes / (1024*1024):.2f} MB")

    # Build request
    print("\nBuilding inference request...")
    request = build_request(audio)
    print(f"  Request size: {len(request) / (1024*1024):.2f} MB")

    # Send request
    print("\nSending inference request (this may take a while on phone)...")
    start = time.time()

    try:
        response = requests.post(
            f"{SERVER_URL}/inference_binary",
            data=request,
            headers={"Content-Type": "application/octet-stream"},
            timeout=600  # 10 minute timeout for slow phone
        )
    except requests.exceptions.Timeout:
        print("  Request timed out after 10 minutes")
        return
    except Exception as e:
        print(f"  Request failed: {e}")
        return

    elapsed = time.time() - start
    rtf = duration / elapsed if elapsed > 0 else 0

    print(f"  Response received in {elapsed:.2f}s")
    print(f"  Response size: {len(response.content) / (1024*1024):.2f} MB")

    # Parse response
    result = parse_response(response.content)

    if "error" in result:
        print(f"\nError from server: {result['error']}")
        return

    print(f"\nResults:")
    print(f"  Status: {result['status']}")
    print(f"  Stems received: {list(result['stems'].keys())}")

    for name, info in result['stems'].items():
        print(f"    {name}: shape={info['shape']}, size={info['size_mb']:.2f}MB")

    print(f"\nPerformance:")
    print(f"  Audio duration: {duration:.1f}s")
    print(f"  Processing time: {elapsed:.2f}s")
    print(f"  RTF: {rtf:.3f}x realtime")

    if rtf < 1.0:
        print(f"  Note: {1/rtf:.1f}x slower than realtime")


if __name__ == "__main__":
    main()
