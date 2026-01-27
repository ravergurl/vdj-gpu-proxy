#!/usr/bin/env python3
"""Test the /create_vdjstem endpoint."""

import struct
import requests
import numpy as np
import sys

SERVER_URL = "https://vdj-gpu-direct.ai-smith.net"


def write_uint32(val: int) -> bytes:
    return struct.pack("<I", val)


def write_int64(val: int) -> bytes:
    return struct.pack("<q", val)


def write_string(s: str) -> bytes:
    encoded = s.encode("utf-8")
    return write_uint32(len(encoded)) + encoded


def write_shape(shape: tuple) -> bytes:
    result = write_uint32(len(shape))
    for dim in shape:
        result += write_int64(dim)
    return result


def read_uint32(data: bytes, offset: int) -> tuple:
    val = struct.unpack("<I", data[offset:offset+4])[0]
    return val, offset + 4


def read_string(data: bytes, offset: int) -> tuple:
    length, offset = read_uint32(data, offset)
    s = data[offset:offset+length].decode("utf-8")
    return s, offset + length


def read_shape(data: bytes, offset: int) -> tuple:
    ndim, offset = read_uint32(data, offset)
    shape = []
    for _ in range(ndim):
        dim = struct.unpack("<q", data[offset:offset+8])[0]
        shape.append(dim)
        offset += 8
    return tuple(shape), offset


def test_create_vdjstem():
    """Test the create_vdjstem endpoint with synthetic audio."""
    print("Testing /create_vdjstem endpoint...")
    print(f"Server: {SERVER_URL}")

    # Create synthetic stereo audio (2 channels, 5 seconds at 44100Hz)
    duration_sec = 5
    sample_rate = 44100
    num_samples = duration_sec * sample_rate

    # Generate a simple sine wave with some harmonics
    t = np.linspace(0, duration_sec, num_samples, dtype=np.float32)
    freq = 440  # A4 note
    audio_left = 0.5 * np.sin(2 * np.pi * freq * t) + 0.3 * np.sin(2 * np.pi * freq * 2 * t)
    audio_right = 0.5 * np.sin(2 * np.pi * freq * t) + 0.2 * np.sin(2 * np.pi * freq * 3 * t)

    # Shape: (channels, samples)
    audio = np.stack([audio_left, audio_right]).astype(np.float32)
    print(f"Audio shape: {audio.shape}, dtype: {audio.dtype}")
    print(f"Audio size: {audio.nbytes / (1024*1024):.2f} MB")

    # Build binary request
    session_id = 12345
    audio_shape = audio.shape
    audio_dtype = 1  # FLOAT32
    audio_bytes = audio.tobytes()

    request_buf = write_uint32(session_id)
    request_buf += write_shape(audio_shape)
    request_buf += write_uint32(audio_dtype)
    request_buf += write_uint32(len(audio_bytes))
    request_buf += audio_bytes

    # Request all 4 stems
    stem_names = ["drums", "bass", "other", "vocals"]
    request_buf += write_uint32(len(stem_names))
    for name in stem_names:
        request_buf += write_string(name)

    print(f"Request size: {len(request_buf) / (1024*1024):.2f} MB")

    # Send request
    print("Sending request...")
    try:
        response = requests.post(
            f"{SERVER_URL}/create_vdjstem",
            data=request_buf,
            headers={"Content-Type": "application/octet-stream"},
            timeout=300  # 5 minute timeout
        )
    except requests.exceptions.Timeout:
        print("ERROR: Request timed out")
        return False
    except Exception as e:
        print(f"ERROR: Request failed: {e}")
        return False

    print(f"Response status: {response.status_code}")
    print(f"Response size: {len(response.content) / (1024*1024):.2f} MB")

    if response.status_code != 200:
        print(f"ERROR: Server returned {response.status_code}")
        print(f"Response: {response.content[:500]}")
        return False

    # Parse response
    data = response.content
    offset = 0

    resp_session_id, offset = read_uint32(data, offset)
    print(f"Response session_id: {resp_session_id}")

    status, offset = read_uint32(data, offset)
    print(f"Response status: {status}")

    error_msg, offset = read_string(data, offset)
    if status != 0:
        print(f"ERROR: Server error: {error_msg}")
        return False

    audio_hash, offset = read_string(data, offset)
    print(f"Audio hash: {audio_hash}")

    stem_file_len, offset = read_uint32(data, offset)
    print(f"VDJStem file size: {stem_file_len / 1024:.1f} KB")

    if stem_file_len > 0:
        stem_file_content = data[offset:offset + stem_file_len]
        offset += stem_file_len

        # Save to temp file for inspection
        temp_path = f"/tmp/test_{audio_hash}.vdjstem"
        with open(temp_path, "wb") as f:
            f.write(stem_file_content)
        print(f"Saved VDJStem to: {temp_path}")

    num_outputs, offset = read_uint32(data, offset)
    print(f"Number of output tensors: {num_outputs}")

    for i in range(num_outputs):
        name, offset = read_string(data, offset)
        shape, offset = read_shape(data, offset)
        dtype, offset = read_uint32(data, offset)
        data_len, offset = read_uint32(data, offset)
        offset += data_len  # Skip tensor data
        print(f"  Output[{i}]: {name}, shape={shape}, dtype={dtype}, size={data_len/(1024*1024):.2f} MB")

    print("\nSUCCESS: /create_vdjstem endpoint working correctly!")
    return True


if __name__ == "__main__":
    success = test_create_vdjstem()
    sys.exit(0 if success else 1)
