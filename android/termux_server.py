#!/usr/bin/env python3
"""
VDJ Stems Server for Termux (Pixel 8 Pro)
Minimal HTTP server compatible with existing proxy DLL binary protocol.
"""

import struct
import logging
import argparse
import time
from typing import Generator
import numpy as np

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Lazy imports for faster startup feedback
torch = None
demucs_model = None
DEVICE = "cpu"


def lazy_load_model(model_name: str = "htdemucs"):
    """Load model on first inference request."""
    global torch, demucs_model, DEVICE

    if demucs_model is not None:
        return

    logger.info("Loading PyTorch...")
    import torch as _torch
    torch = _torch

    # Check available devices
    if torch.cuda.is_available():
        DEVICE = "cuda"
        logger.info(f"CUDA available: {torch.cuda.get_device_name(0)}")
    else:
        DEVICE = "cpu"
        # Check for ARM optimizations
        logger.info(f"Using CPU (threads: {torch.get_num_threads()})")

    logger.info(f"Loading Demucs model '{model_name}'...")
    from demucs import pretrained
    demucs_model = pretrained.get_model(model_name)
    demucs_model.to(DEVICE)
    demucs_model.eval()
    logger.info(f"Model loaded on {DEVICE}")


def separate_audio(audio: np.ndarray, sample_rate: int = 44100) -> dict:
    """
    Separate audio into stems using Demucs.
    audio: shape (channels, samples)
    Returns: dict of stem_name -> np.ndarray
    """
    lazy_load_model()

    from demucs.apply import apply_model

    # Ensure stereo
    if audio.ndim == 1:
        audio = np.stack([audio, audio])

    if audio.shape[0] > 2:
        audio = audio.T

    duration_sec = audio.shape[1] / sample_rate
    logger.info(f"Processing {duration_sec:.2f}s audio, shape={audio.shape}")

    # Convert to tensor
    audio_tensor = torch.from_numpy(audio).float().to(DEVICE)
    if audio_tensor.dim() == 2:
        audio_tensor = audio_tensor.unsqueeze(0)

    # Run inference
    start = time.time()
    with torch.no_grad():
        sources = apply_model(
            demucs_model,
            audio_tensor,
            device=DEVICE,
            shifts=1,
            split=True,
            overlap=0.25,
            progress=False,
        )[0]

    elapsed = time.time() - start
    rtf = duration_sec / elapsed if elapsed > 0 else 0
    logger.info(f"Inference took {elapsed:.2f}s (RTF: {rtf:.2f}x)")

    # Extract stems
    stems = {}
    for i, name in enumerate(demucs_model.sources):
        stems[name] = sources[i].cpu().numpy()

    return stems


class BinaryProtocol:
    """Binary protocol for VDJ proxy DLL communication."""

    @staticmethod
    def read_uint32(data: bytes, offset: int) -> tuple:
        value = struct.unpack("<I", data[offset:offset+4])[0]
        return value, offset + 4

    @staticmethod
    def read_string(data: bytes, offset: int) -> tuple:
        length, offset = BinaryProtocol.read_uint32(data, offset)
        string = data[offset:offset+length].decode("utf-8")
        return string, offset + length

    @staticmethod
    def read_shape(data: bytes, offset: int) -> tuple:
        ndim, offset = BinaryProtocol.read_uint32(data, offset)
        shape = []
        for _ in range(ndim):
            dim = struct.unpack("<q", data[offset:offset+8])[0]
            shape.append(dim)
            offset += 8
        return tuple(shape), offset

    @staticmethod
    def write_uint32(value: int) -> bytes:
        return struct.pack("<I", value)

    @staticmethod
    def write_string(s: str) -> bytes:
        encoded = s.encode("utf-8")
        return BinaryProtocol.write_uint32(len(encoded)) + encoded

    @staticmethod
    def write_shape(shape: tuple) -> bytes:
        result = BinaryProtocol.write_uint32(len(shape))
        for dim in shape:
            result += struct.pack("<q", dim)
        return result

    @staticmethod
    def write_tensor(name: str, shape: tuple, dtype: int, data: bytes) -> bytes:
        result = BinaryProtocol.write_string(name)
        result += BinaryProtocol.write_shape(shape)
        result += BinaryProtocol.write_uint32(dtype)
        result += BinaryProtocol.write_uint32(len(data))
        result += data
        return result


def parse_request(body: bytes) -> tuple:
    """Parse binary inference request."""
    offset = 0
    session_id, offset = BinaryProtocol.read_uint32(body, offset)
    num_inputs, offset = BinaryProtocol.read_uint32(body, offset)

    audio_data = None
    audio_shape = None

    for _ in range(num_inputs):
        input_name, offset = BinaryProtocol.read_string(body, offset)
        input_shape, offset = BinaryProtocol.read_shape(body, offset)
        input_dtype, offset = BinaryProtocol.read_uint32(body, offset)
        input_data_len, offset = BinaryProtocol.read_uint32(body, offset)
        input_data_buf = body[offset:offset+input_data_len]
        offset += input_data_len

        # Audio is 2D: [channels, samples]
        if len(input_shape) == 2 and audio_data is None:
            audio_data = input_data_buf
            audio_shape = input_shape

    if audio_data is None:
        raise ValueError(f"No 2D audio input found among {num_inputs} inputs")

    # Read output names
    num_outputs, offset = BinaryProtocol.read_uint32(body, offset)
    output_names = []
    for _ in range(num_outputs):
        name, offset = BinaryProtocol.read_string(body, offset)
        output_names.append(name)

    return session_id, audio_data, audio_shape, output_names


def build_response(session_id: int, stems: dict, output_names: list) -> bytes:
    """Build binary response with all stems."""
    # Header
    response = BinaryProtocol.write_uint32(session_id)
    response += BinaryProtocol.write_uint32(0)  # status = success
    response += BinaryProtocol.write_uint32(0)  # no error message
    response += BinaryProtocol.write_uint32(len(output_names))

    # Stems
    for name in output_names:
        if name in stems:
            stem_data = stems[name]
            response += BinaryProtocol.write_tensor(
                name=name,
                shape=stem_data.shape,
                dtype=1,  # FLOAT32
                data=stem_data.tobytes()
            )

    return response


def build_error_response(session_id: int, error_msg: str) -> bytes:
    """Build binary error response."""
    response = BinaryProtocol.write_uint32(session_id)
    response += BinaryProtocol.write_uint32(1)  # status = error
    response += BinaryProtocol.write_string(error_msg)
    response += BinaryProtocol.write_uint32(0)  # no outputs
    return response


# ============ HTTP Server ============

from http.server import HTTPServer, BaseHTTPRequestHandler
import io


class InferenceHandler(BaseHTTPRequestHandler):
    """HTTP handler for inference requests."""

    protocol_version = 'HTTP/1.1'

    def log_message(self, format, *args):
        logger.info(f"{self.client_address[0]} - {format % args}")

    def do_GET(self):
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.end_headers()
            self.wfile.write(b'{"status":"ok"}')
        else:
            self.send_error(404)

    def do_POST(self):
        if self.path != "/inference_binary":
            self.send_error(404)
            return

        try:
            # Read request body
            content_length = int(self.headers.get("Content-Length", 0))
            body = self.rfile.read(content_length)

            # Parse request
            session_id, audio_data, audio_shape, output_names = parse_request(body)
            logger.info(f"Session {session_id}: shape={audio_shape}, outputs={output_names}")

            # Convert to numpy and separate
            audio = np.frombuffer(audio_data, dtype=np.float32).reshape(audio_shape)
            stems = separate_audio(audio)

            # Build response
            response = build_response(session_id, stems, output_names)

            # Send response
            self.send_response(200)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(response)))
            self.end_headers()
            self.wfile.write(response)

        except Exception as e:
            logger.exception(f"Inference error: {e}")
            error_response = build_error_response(0, str(e))
            self.send_response(400)
            self.send_header("Content-Type", "application/octet-stream")
            self.send_header("Content-Length", str(len(error_response)))
            self.end_headers()
            self.wfile.write(error_response)


def run_server(host: str = "0.0.0.0", port: int = 8081):
    """Run the HTTP server."""
    server = HTTPServer((host, port), InferenceHandler)
    logger.info(f"Starting server on {host}:{port}")
    logger.info("Model will be loaded on first inference request")
    logger.info("Press Ctrl+C to stop")

    try:
        server.serve_forever()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
        server.shutdown()


def main():
    parser = argparse.ArgumentParser(description="VDJ Stems Server for Termux")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=8081, help="Port to listen on")
    parser.add_argument("--preload", action="store_true", help="Preload model at startup")
    args = parser.parse_args()

    if args.preload:
        logger.info("Preloading model...")
        lazy_load_model()

    run_server(args.host, args.port)


if __name__ == "__main__":
    main()
