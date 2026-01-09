"""
HTTP streaming endpoint for progressive stem delivery.
Uses binary format and chunked encoding instead of JSON/base64.
"""

import struct
import logging
from typing import AsyncGenerator
from fastapi import FastAPI, Request, Response
from fastapi.responses import StreamingResponse
import numpy as np

from .inference import get_engine

logger = logging.getLogger(__name__)

app = FastAPI()


class BinaryProtocol:
    """
    Binary protocol for efficient stem transfer.

    Request format:
        [4 bytes] session_id (uint32)
        [4 bytes] num_inputs (uint32)
        For each input:
            [4 bytes] name_len (uint32)
            [name_len bytes] name (UTF-8)
            [4 bytes] ndim (uint32)
            [ndim * 8 bytes] shape (int64[])
            [4 bytes] dtype (uint32)
            [4 bytes] data_len (uint32)
            [data_len bytes] data (raw bytes)
        [4 bytes] num_outputs (uint32)
        For each output:
            [4 bytes] name_len (uint32)
            [name_len bytes] name (UTF-8)

    Response format (streamed):
        [4 bytes] session_id (uint32)
        [4 bytes] status (uint32) - 0=success, non-zero=error
        [4 bytes] error_msg_len (uint32)
        [error_msg_len bytes] error_message (UTF-8)
        [4 bytes] num_outputs (uint32)
        For each output (streamed as ready):
            [4 bytes] name_len (uint32)
            [name_len bytes] name (UTF-8)
            [4 bytes] ndim (uint32)
            [ndim * 8 bytes] shape (int64[])
            [4 bytes] dtype (uint32)
            [4 bytes] data_len (uint32)
            [data_len bytes] data (raw bytes)
    """

    @staticmethod
    def read_uint32(data: bytes, offset: int) -> tuple[int, int]:
        """Read uint32 and return (value, new_offset)"""
        value = struct.unpack("<I", data[offset:offset+4])[0]
        return value, offset + 4

    @staticmethod
    def read_string(data: bytes, offset: int) -> tuple[str, int]:
        """Read length-prefixed string and return (string, new_offset)"""
        length, offset = BinaryProtocol.read_uint32(data, offset)
        string = data[offset:offset+length].decode("utf-8")
        return string, offset + length

    @staticmethod
    def read_shape(data: bytes, offset: int) -> tuple[tuple[int, ...], int]:
        """Read shape array and return (shape_tuple, new_offset)"""
        ndim, offset = BinaryProtocol.read_uint32(data, offset)
        shape = []
        for _ in range(ndim):
            dim = struct.unpack("<q", data[offset:offset+8])[0]
            shape.append(dim)
            offset += 8
        return tuple(shape), offset

    @staticmethod
    def write_uint32(value: int) -> bytes:
        """Write uint32 to bytes"""
        return struct.pack("<I", value)

    @staticmethod
    def write_string(s: str) -> bytes:
        """Write length-prefixed string"""
        encoded = s.encode("utf-8")
        return BinaryProtocol.write_uint32(len(encoded)) + encoded

    @staticmethod
    def write_shape(shape: tuple[int, ...]) -> bytes:
        """Write shape array"""
        result = BinaryProtocol.write_uint32(len(shape))
        for dim in shape:
            result += struct.pack("<q", dim)
        return result

    @staticmethod
    def write_tensor(name: str, shape: tuple[int, ...], dtype: int, data: bytes) -> bytes:
        """Write complete tensor"""
        result = BinaryProtocol.write_string(name)
        result += BinaryProtocol.write_shape(shape)
        result += BinaryProtocol.write_uint32(dtype)
        result += BinaryProtocol.write_uint32(len(data))
        result += data
        return result


async def stream_stems_binary(
    session_id: int,
    audio_data: bytes,
    audio_shape: tuple[int, ...],
    output_names: list[str]
) -> AsyncGenerator[bytes, None]:
    """
    Process audio and stream stems as they're generated.
    """
    try:
        engine = get_engine()

        # Parse audio tensor
        audio = np.frombuffer(audio_data, dtype=np.float32).reshape(audio_shape)

        # Separate stems
        logger.info(f"Session {session_id}: Separating stems for shape {audio_shape}")
        stems = engine.separate(audio)

        # Stream header
        header = BinaryProtocol.write_uint32(session_id)
        header += BinaryProtocol.write_uint32(0)  # status = success
        header += BinaryProtocol.write_uint32(0)  # no error message
        header += BinaryProtocol.write_uint32(len(output_names))  # num outputs
        yield header

        # Stream each stem as it's ready
        for name in output_names:
            if name not in stems:
                logger.warning(f"Requested stem '{name}' not in results")
                continue

            stem_data = stems[name]
            logger.info(f"Session {session_id}: Streaming stem '{name}' shape={stem_data.shape}")

            tensor_bytes = BinaryProtocol.write_tensor(
                name=name,
                shape=stem_data.shape,
                dtype=1,  # FLOAT32
                data=stem_data.tobytes()
            )
            yield tensor_bytes

    except Exception as e:
        logger.exception(f"Session {session_id}: Error during stem separation")
        # Send error response
        error_msg = str(e)
        error_response = BinaryProtocol.write_uint32(session_id)
        error_response += BinaryProtocol.write_uint32(1)  # status = error
        error_response += BinaryProtocol.write_string(error_msg)
        error_response += BinaryProtocol.write_uint32(0)  # no outputs
        yield error_response


@app.post("/inference_binary")
async def inference_binary(request: Request):
    """
    Binary streaming inference endpoint.
    Accepts binary request, returns binary response with chunked encoding.
    """
    # Read binary request
    body = await request.body()

    try:
        # Parse request
        offset = 0
        session_id, offset = BinaryProtocol.read_uint32(body, offset)
        num_inputs, offset = BinaryProtocol.read_uint32(body, offset)

        # Read all inputs and find the audio tensor (2D with shape [channels, samples])
        audio_data = None
        audio_shape = None

        for i in range(num_inputs):
            input_name, offset = BinaryProtocol.read_string(body, offset)
            input_shape, offset = BinaryProtocol.read_shape(body, offset)
            input_dtype, offset = BinaryProtocol.read_uint32(body, offset)
            input_data_len, offset = BinaryProtocol.read_uint32(body, offset)
            input_data_buf = body[offset:offset+input_data_len]
            offset += input_data_len

            # Audio tensor is 2D: [channels, samples]
            # Other inputs (spectrograms, etc.) are 3D or 4D
            if len(input_shape) == 2:
                logger.info(f"Found audio input: name={input_name}, shape={input_shape}")
                audio_data = input_data_buf
                audio_shape = input_shape
                break  # Use first 2D tensor as audio

        if audio_data is None:
            raise ValueError(f"No 2D audio input found among {num_inputs} inputs")

        # Read output names
        num_outputs, offset = BinaryProtocol.read_uint32(body, offset)
        output_names = []
        for _ in range(num_outputs):
            name, offset = BinaryProtocol.read_string(body, offset)
            output_names.append(name)

        logger.info(f"Binary inference: session={session_id}, input_shape={audio_shape}, outputs={output_names}")

        # Return streaming response
        return StreamingResponse(
            stream_stems_binary(session_id, audio_data, audio_shape, output_names),
            media_type="application/octet-stream"
        )

    except Exception as e:
        logger.exception("Failed to parse binary request")
        return Response(
            content=f"Error: {e}".encode("utf-8"),
            status_code=400
        )


@app.get("/health")
async def health():
    return {"status": "ok"}


def run_streaming_server(host: str = "0.0.0.0", port: int = 8081):
    """Run the streaming HTTP server"""
    import uvicorn
    uvicorn.run(app, host=host, port=port, log_level="info")
