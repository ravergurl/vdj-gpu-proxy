import grpc
from concurrent import futures
import numpy as np
import logging
from . import stems_pb2
from . import stems_pb2_grpc
from .inference import get_engine, STEM_NAMES

logger = logging.getLogger(__name__)


class StemsInferenceServicer(stems_pb2_grpc.StemsInferenceServicer):
    def __init__(self, engine_kwargs=None):
        self.engine = get_engine(**(engine_kwargs or {}))

    def GetServerInfo(self, request, context):
        return stems_pb2.ServerInfo(
            version="1.0.0",
            model_name=self.engine.model_name,
            gpu_memory_mb=self.engine.gpu_memory_mb,
            ready=True,
        )

    def RunInference(self, request, context):
        try:
            if not request.inputs:
                return stems_pb2.InferenceResponse(
                    session_id=request.session_id,
                    status=1,
                    error_message="No input tensors provided",
                )

            input_tensor = request.inputs[0]
            shape = tuple(input_tensor.shape.dims)

            if not shape or len(shape) < 2:
                return stems_pb2.InferenceResponse(
                    session_id=request.session_id,
                    status=1,
                    error_message=f"Invalid tensor shape: {shape}",
                )

            stems_bytes, out_shape = self.engine.separate_tensor(
                input_tensor.data, shape, input_tensor.dtype
            )

            outputs = []
            requested = request.output_names if request.output_names else STEM_NAMES

            for name in requested:
                if name in stems_bytes:
                    outputs.append(
                        stems_pb2.Tensor(
                            shape=stems_pb2.TensorShape(dims=list(out_shape)),
                            dtype=input_tensor.dtype,
                            data=stems_bytes[name],
                        )
                    )
                else:
                    logger.warning(f"Requested stem '{name}' not found in model output")

            if not outputs:
                return stems_pb2.InferenceResponse(
                    session_id=request.session_id,
                    status=1,
                    error_message="No output stems generated",
                )

            return stems_pb2.InferenceResponse(
                session_id=request.session_id, status=0, outputs=outputs
            )
        except ValueError as e:
            logger.warning(f"Invalid input for session {request.session_id}: {e}")
            return stems_pb2.InferenceResponse(
                session_id=request.session_id,
                status=400,
                error_message=str(e),
            )
        except RuntimeError as e:
            logger.error(f"Inference runtime error for session {request.session_id}: {e}")
            return stems_pb2.InferenceResponse(
                session_id=request.session_id,
                status=500,
                error_message=str(e),
            )
        except Exception as e:
            logger.exception(f"Unexpected error for session {request.session_id}")
            return stems_pb2.InferenceResponse(
                session_id=request.session_id, status=1, error_message=str(e)
            )

    def StreamInference(self, request_iterator, context):
        try:
            for chunk in request_iterator:
                if chunk.channels <= 0:
                    logger.warning(f"Invalid channel count: {chunk.channels}")
                    continue

                audio = np.frombuffer(chunk.audio_data, dtype=np.float32).reshape(
                    chunk.channels, -1
                )
                stems = self.engine.separate(audio, sample_rate=chunk.sample_rate)

                for name, data in stems.items():
                    yield stems_pb2.StemChunk(
                        session_id=chunk.session_id,
                        chunk_index=chunk.chunk_index,
                        stem_name=name,
                        audio_data=data.tobytes(),
                    )
        except Exception as e:
            logger.exception(f"StreamInference error")
            context.abort(grpc.StatusCode.INTERNAL, str(e))


def serve(host="0.0.0.0", port=50051, max_workers=10):
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=max_workers),
        options=[
            ("grpc.max_send_message_length", 100 * 1024 * 1024),
            ("grpc.max_receive_message_length", 100 * 1024 * 1024),
        ],
    )
    stems_pb2_grpc.add_StemsInferenceServicer_to_server(StemsInferenceServicer(), server)
    server.add_insecure_port(f"{host}:{port}")
    server.start()
    return server
