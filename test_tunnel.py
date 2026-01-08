#!/usr/bin/env python3
"""Test Cloudflare tunnel connection to gRPC server."""

import grpc
import sys
import os

# Add server to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "server", "src"))

from vdj_stems_server import stems_pb2, stems_pb2_grpc


def test_tunnel(tunnel_url: str):
    """Test connection through Cloudflare tunnel."""
    # Remove https:// prefix and extract host
    host = tunnel_url.replace("https://", "").replace("http://", "")

    print(f"Testing tunnel: {host}:443 (SSL)")

    # Create SSL credentials for Cloudflare
    credentials = grpc.ssl_channel_credentials()

    # Create secure channel
    channel = grpc.secure_channel(
        f"{host}:443",
        credentials,
        options=[
            ("grpc.max_receive_message_length", 100 * 1024 * 1024),
            ("grpc.max_send_message_length", 100 * 1024 * 1024),
            ("grpc.keepalive_time_ms", 30000),
            ("grpc.keepalive_timeout_ms", 10000),
        ],
    )

    try:
        # Wait for channel to be ready
        grpc.channel_ready_future(channel).result(timeout=10.0)
        print("✓ Channel connected")

        # Test GetServerInfo RPC
        stub = stems_pb2_grpc.StemsInferenceStub(channel)
        response = stub.GetServerInfo(stems_pb2.Empty(), timeout=10.0)

        print("✓ Server responded:")
        print(f"  Version: {response.version}")
        print(f"  Model: {response.model_name}")
        print(f"  GPU Memory: {response.gpu_memory_mb} MB")
        print(f"  Ready: {response.ready}")

        if response.ready:
            print("\n✓✓✓ TUNNEL WORKS! ✓✓✓")
            return True
        else:
            print("\n⚠ Server not ready")
            return False

    except grpc.FutureTimeoutError:
        print("✗ Connection timeout - tunnel might be down")
        return False
    except grpc.RpcError as e:
        print(f"✗ RPC Error: {e.code()} - {e.details()}")
        return False
    except Exception as e:
        print(f"✗ Error: {e}")
        return False
    finally:
        channel.close()


if __name__ == "__main__":
    tunnel_url = (
        sys.argv[1]
        if len(sys.argv) > 1
        else "https://creator-radar-request-opponents.trycloudflare.com"
    )
    success = test_tunnel(tunnel_url)
    sys.exit(0 if success else 1)
