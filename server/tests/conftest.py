import pytest
import numpy as np


@pytest.fixture
def sample_audio():
    sample_rate = 44100
    duration = 1.0
    num_samples = int(sample_rate * duration)
    return np.random.randn(2, num_samples).astype(np.float32)


@pytest.fixture
def mock_grpc_channel(mocker):
    channel = mocker.MagicMock()
    mocker.patch("grpc.insecure_channel", return_value=channel)
    return channel
