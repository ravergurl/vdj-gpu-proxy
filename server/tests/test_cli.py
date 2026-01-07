import pytest
from unittest.mock import MagicMock, patch
import sys


class TestHealthCheck:
    def test_health_check_healthy(self, mocker):
        mock_channel = MagicMock()
        mock_stub = MagicMock()
        mock_response = MagicMock()
        mock_response.version = "1.0.0"
        mock_response.model_name = "htdemucs"
        mock_response.gpu_memory_mb = 8192
        mock_response.ready = True

        mock_stub.GetServerInfo.return_value = mock_response

        mocker.patch("vdj_stems_server.cli.create_channel", return_value=mock_channel)
        mocker.patch(
            "vdj_stems_server.cli.stems_pb2_grpc.StemsInferenceStub", return_value=mock_stub
        )
        mocker.patch("vdj_stems_server.cli.stems_pb2")
        mocker.patch("sys.argv", ["vdj-stems-health", "--host", "localhost", "--port", "50051"])

        from vdj_stems_server.cli import health_check

        with pytest.raises(SystemExit) as exc_info:
            health_check()

        assert exc_info.value.code == 0

    def test_health_check_connection_failed(self, mocker):
        mocker.patch("vdj_stems_server.cli.create_channel", return_value=None)
        mocker.patch("vdj_stems_server.cli.stems_pb2")
        mocker.patch("sys.argv", ["vdj-stems-health"])

        from vdj_stems_server.cli import health_check

        with pytest.raises(SystemExit) as exc_info:
            health_check()

        assert exc_info.value.code == 1


class TestStatus:
    def test_status_online(self, mocker, capsys):
        mock_channel = MagicMock()
        mock_stub = MagicMock()
        mock_response = MagicMock()
        mock_response.version = "1.0.0"
        mock_response.model_name = "htdemucs"
        mock_response.gpu_memory_mb = 8192
        mock_response.ready = True

        mock_stub.GetServerInfo.return_value = mock_response

        mocker.patch("vdj_stems_server.cli.create_channel", return_value=mock_channel)
        mocker.patch(
            "vdj_stems_server.cli.stems_pb2_grpc.StemsInferenceStub", return_value=mock_stub
        )
        mocker.patch("vdj_stems_server.cli.stems_pb2")
        mocker.patch("sys.argv", ["vdj-stems-status"])

        from vdj_stems_server.cli import status

        status()

        captured = capsys.readouterr()
        assert "ONLINE" in captured.out

    def test_status_offline(self, mocker, capsys):
        mocker.patch("vdj_stems_server.cli.create_channel", return_value=None)
        mocker.patch("vdj_stems_server.cli.stems_pb2")
        mocker.patch("sys.argv", ["vdj-stems-status"])

        from vdj_stems_server.cli import status

        with pytest.raises(SystemExit):
            status()

        captured = capsys.readouterr()
        assert "OFFLINE" in captured.out

    def test_status_json_output(self, mocker, capsys):
        mock_channel = MagicMock()
        mock_stub = MagicMock()
        mock_response = MagicMock()
        mock_response.version = "1.0.0"
        mock_response.model_name = "htdemucs"
        mock_response.gpu_memory_mb = 8192
        mock_response.ready = True

        mock_stub.GetServerInfo.return_value = mock_response

        mocker.patch("vdj_stems_server.cli.create_channel", return_value=mock_channel)
        mocker.patch(
            "vdj_stems_server.cli.stems_pb2_grpc.StemsInferenceStub", return_value=mock_stub
        )
        mocker.patch("vdj_stems_server.cli.stems_pb2")
        mocker.patch("sys.argv", ["vdj-stems-status", "--json"])

        from vdj_stems_server.cli import status

        status()

        captured = capsys.readouterr()
        assert '"status":' in captured.out
        assert '"online"' in captured.out


class TestCreateChannel:
    def test_create_channel_success(self, mocker):
        mock_channel = MagicMock()
        mock_future = MagicMock()

        mocker.patch("grpc.insecure_channel", return_value=mock_channel)
        mocker.patch("grpc.channel_ready_future", return_value=mock_future)

        from vdj_stems_server.cli import create_channel

        result = create_channel("localhost", 50051)

        assert result is mock_channel

    def test_create_channel_timeout(self, mocker):
        import grpc

        mock_channel = MagicMock()
        mock_future = MagicMock()
        mock_future.result.side_effect = grpc.FutureTimeoutError()

        mocker.patch("grpc.insecure_channel", return_value=mock_channel)
        mocker.patch("grpc.channel_ready_future", return_value=mock_future)

        from vdj_stems_server.cli import create_channel

        result = create_channel("localhost", 50051, timeout=0.1)

        assert result is None
