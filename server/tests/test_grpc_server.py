import pytest
from unittest.mock import MagicMock, patch
import numpy as np


class TestStemsInferenceServicer:
    @pytest.fixture
    def mock_engine(self, mocker):
        engine = MagicMock()
        engine.model_name = "htdemucs"
        engine.gpu_memory_mb = 8192
        engine.separate_tensor.return_value = (
            {
                "drums": np.zeros((2, 44100), dtype=np.float32).tobytes(),
                "bass": np.zeros((2, 44100), dtype=np.float32).tobytes(),
                "other": np.zeros((2, 44100), dtype=np.float32).tobytes(),
                "vocals": np.zeros((2, 44100), dtype=np.float32).tobytes(),
            },
            (2, 44100),
        )
        return engine

    @pytest.fixture
    def servicer(self, mock_engine, mocker):
        mocker.patch("vdj_stems_server.grpc_server.get_engine", return_value=mock_engine)
        from vdj_stems_server.grpc_server import StemsInferenceServicer

        return StemsInferenceServicer(engine_kwargs={})

    def test_get_server_info(self, servicer, mock_engine):
        from vdj_stems_server import stems_pb2

        request = stems_pb2.Empty()
        context = MagicMock()

        response = servicer.GetServerInfo(request, context)

        assert response.version == "1.0.0"
        assert response.model_name == "htdemucs"
        assert response.gpu_memory_mb == 8192
        assert response.ready is True

    def test_run_inference_success(self, servicer, mock_engine):
        from vdj_stems_server import stems_pb2

        audio_data = np.random.randn(2, 44100).astype(np.float32)

        request = stems_pb2.InferenceRequest(
            session_id=1,
            input_names=["audio"],
            inputs=[
                stems_pb2.Tensor(
                    shape=stems_pb2.TensorShape(dims=[2, 44100]),
                    dtype=1,
                    data=audio_data.tobytes(),
                )
            ],
            output_names=["drums", "bass", "other", "vocals"],
        )
        context = MagicMock()

        response = servicer.RunInference(request, context)

        assert response.status == 0
        assert len(response.outputs) == 4

    def test_run_inference_no_inputs(self, servicer):
        from vdj_stems_server import stems_pb2

        request = stems_pb2.InferenceRequest(
            session_id=1,
            input_names=[],
            inputs=[],
            output_names=["drums"],
        )
        context = MagicMock()

        response = servicer.RunInference(request, context)

        assert response.status == 1
        assert "No input" in response.error_message

    def test_run_inference_invalid_shape(self, servicer):
        from vdj_stems_server import stems_pb2

        request = stems_pb2.InferenceRequest(
            session_id=1,
            input_names=["audio"],
            inputs=[
                stems_pb2.Tensor(
                    shape=stems_pb2.TensorShape(dims=[]),
                    dtype=1,
                    data=b"",
                )
            ],
            output_names=["drums"],
        )
        context = MagicMock()

        response = servicer.RunInference(request, context)

        assert response.status == 1
        assert "Invalid" in response.error_message


class TestServe:
    def test_serve_creates_server(self, mocker):
        mock_server = MagicMock()
        mocker.patch("grpc.server", return_value=mock_server)
        mocker.patch("vdj_stems_server.grpc_server.get_engine")

        from vdj_stems_server.grpc_server import serve

        server = serve(host="0.0.0.0", port=50051)

        assert server is mock_server
        mock_server.add_insecure_port.assert_called_once_with("0.0.0.0:50051")
        mock_server.start.assert_called_once()
