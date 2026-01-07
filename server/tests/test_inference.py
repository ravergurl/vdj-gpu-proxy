import pytest
import numpy as np
from unittest.mock import MagicMock, patch


class TestStemsInferenceEngine:
    @pytest.fixture
    def mock_demucs(self, mocker):
        mock_model = MagicMock()
        mock_model.samplerate = 44100
        mock_model.sources = ["drums", "bass", "other", "vocals"]

        mocker.patch("vdj_stems_server.inference.pretrained.get_model", return_value=mock_model)
        return mock_model

    def test_engine_init_cpu(self, mock_demucs):
        with patch("torch.cuda.is_available", return_value=False):
            from vdj_stems_server.inference import StemsInferenceEngine

            engine = StemsInferenceEngine(device="cpu")
            assert engine.device == "cpu"
            assert engine.model_name == "htdemucs"

    def test_engine_init_cuda_fallback(self, mock_demucs):
        with patch("torch.cuda.is_available", return_value=False):
            from vdj_stems_server.inference import StemsInferenceEngine

            engine = StemsInferenceEngine(device="cuda")
            assert engine.device == "cpu"

    def test_gpu_memory_cpu(self, mock_demucs):
        with patch("torch.cuda.is_available", return_value=False):
            from vdj_stems_server.inference import StemsInferenceEngine

            engine = StemsInferenceEngine(device="cpu")
            assert engine.gpu_memory_mb == 0

    def test_separate_mono_to_stereo(self, mock_demucs, mocker):
        with patch("torch.cuda.is_available", return_value=False):
            from vdj_stems_server.inference import StemsInferenceEngine

            mock_sources = np.random.randn(4, 2, 44100).astype(np.float32)
            mocker.patch(
                "vdj_stems_server.inference.apply_model", return_value=mock_sources[np.newaxis, ...]
            )

            engine = StemsInferenceEngine(device="cpu")
            mono_audio = np.random.randn(44100).astype(np.float32)

            result = engine.separate(mono_audio)

            assert "drums" in result
            assert "bass" in result
            assert "other" in result
            assert "vocals" in result

    def test_separate_stereo(self, mock_demucs, mocker):
        with patch("torch.cuda.is_available", return_value=False):
            from vdj_stems_server.inference import StemsInferenceEngine

            mock_sources = np.random.randn(4, 2, 44100).astype(np.float32)
            mocker.patch(
                "vdj_stems_server.inference.apply_model", return_value=mock_sources[np.newaxis, ...]
            )

            engine = StemsInferenceEngine(device="cpu")
            stereo_audio = np.random.randn(2, 44100).astype(np.float32)

            result = engine.separate(stereo_audio)

            assert len(result) == 4
            for name, data in result.items():
                assert data.shape == (2, 44100)


class TestGetEngine:
    def test_get_engine_singleton(self, mocker):
        mock_model = MagicMock()
        mock_model.samplerate = 44100
        mock_model.sources = ["drums", "bass", "other", "vocals"]

        mocker.patch("vdj_stems_server.inference.pretrained.get_model", return_value=mock_model)

        with patch("torch.cuda.is_available", return_value=False):
            import vdj_stems_server.inference as inf

            inf._engine = None

            engine1 = inf.get_engine()
            engine2 = inf.get_engine()

            assert engine1 is engine2
