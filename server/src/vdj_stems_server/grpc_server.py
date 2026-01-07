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
            input_tensor = request.inputs[0]
            shape = tuple(input_tensor.shape.dims)

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

            return stems_pb2.InferenceResponse(
                session_id=request.session_id, status=0, outputs=outputs
            )
        except Exception as e:
            logger.error(f"Inference error: {e}")
            return stems_pb2.InferenceResponse(
                session_id=request.session_id, status=1, error_message=str(e)
            )

    def StreamInference(self, request_iterator, context):
        for chunk in request_iterator:
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


def serve(host="0.0.0.0", port=50051, max_workers=10):
    server = grpc.server(
        futures.ThreadPoolExecutor(max_workers=max_workers),
        options=[
            ("grpc.max_send_message_length", 100 * 1024 * 1024),
            ("grpc.max_receive_message_length", 100 * 1024 * 1024),
        ],
    )
    stems_pb2_grpc.add_StemsInferenceServicer_to_server(
        StemsInferenceServicer(), server
    )
    server.add_insecure_port(f"{host}:{port}")
    server.start()
    return server
