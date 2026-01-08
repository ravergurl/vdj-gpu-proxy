import argparse
import sys
import time
import grpc
import numpy as np
from typing import Optional

try:
    from . import stems_pb2
    from . import stems_pb2_grpc
except ImportError:
    stems_pb2 = None
    stems_pb2_grpc = None


def create_channel(
    host: str, port: int, timeout: float = 5.0, use_ssl: bool = False
) -> Optional[grpc.Channel]:
    target = f"{host}:{port}"
    options = [
        ("grpc.max_receive_message_length", 100 * 1024 * 1024),
        ("grpc.max_send_message_length", 100 * 1024 * 1024),
    ]

    if use_ssl or port == 443:
        # Use SSL for HTTPS tunnels (port 443) or when explicitly requested
        credentials = grpc.ssl_channel_credentials()
        channel = grpc.secure_channel(target, credentials, options=options)
    else:
        # Use insecure channel for local connections
        channel = grpc.insecure_channel(target, options=options)

    try:
        grpc.channel_ready_future(channel).result(timeout=timeout)
        return channel
    except grpc.FutureTimeoutError:
        return None


def health_check():
    parser = argparse.ArgumentParser(description="Check VDJ Stems Server health")
    parser.add_argument("--host", default="127.0.0.1", help="Server host")
    parser.add_argument("--port", type=int, default=50051, help="Server port")
    parser.add_argument("--timeout", type=float, default=5.0, help="Connection timeout")
    args = parser.parse_args()

    if stems_pb2 is None:
        print("ERROR: Proto files not generated. Run: python scripts/generate_proto.py")
        sys.exit(1)

    print(f"Checking server at {args.host}:{args.port}...")

    channel = create_channel(args.host, args.port, args.timeout)
    if channel is None:
        print(f"UNHEALTHY: Cannot connect to {args.host}:{args.port}")
        sys.exit(1)

    try:
        stub = stems_pb2_grpc.StemsInferenceStub(channel)
        response = stub.GetServerInfo(stems_pb2.Empty(), timeout=args.timeout)

        print(f"HEALTHY")
        print(f"  Version: {response.version}")
        print(f"  Model: {response.model_name}")
        print(f"  GPU Memory: {response.gpu_memory_mb} MB")
        print(f"  Ready: {response.ready}")
        sys.exit(0 if response.ready else 1)
    except grpc.RpcError as e:
        print(f"UNHEALTHY: {e.details()}")
        sys.exit(1)
    finally:
        channel.close()


def status():
    parser = argparse.ArgumentParser(description="Get VDJ Stems Server status")
    parser.add_argument("--host", default="127.0.0.1", help="Server host")
    parser.add_argument("--port", type=int, default=50051, help="Server port")
    parser.add_argument("--json", action="store_true", help="Output as JSON")
    args = parser.parse_args()

    if stems_pb2 is None:
        print("ERROR: Proto files not generated")
        sys.exit(1)

    channel = create_channel(args.host, args.port)
    if channel is None:
        if args.json:
            print('{"status": "offline"}')
        else:
            print("Status: OFFLINE")
        sys.exit(1)

    try:
        stub = stems_pb2_grpc.StemsInferenceStub(channel)
        response = stub.GetServerInfo(stems_pb2.Empty(), timeout=5.0)

        if args.json:
            import json

            print(
                json.dumps(
                    {
                        "status": "online" if response.ready else "not_ready",
                        "version": response.version,
                        "model": response.model_name,
                        "gpu_memory_mb": response.gpu_memory_mb,
                        "ready": response.ready,
                    }
                )
            )
        else:
            status_str = "ONLINE" if response.ready else "NOT READY"
            print(f"Status: {status_str}")
            print(f"Version: {response.version}")
            print(f"Model: {response.model_name}")
            print(f"GPU Memory: {response.gpu_memory_mb} MB")
    except grpc.RpcError as e:
        if args.json:
            print(f'{{"status": "error", "message": "{e.details()}"}}')
        else:
            print(f"Status: ERROR - {e.details()}")
        sys.exit(1)
    finally:
        channel.close()


def benchmark():
    parser = argparse.ArgumentParser(description="Benchmark VDJ Stems Server")
    parser.add_argument("--host", default="127.0.0.1", help="Server host")
    parser.add_argument("--port", type=int, default=50051, help="Server port")
    parser.add_argument("--duration", type=float, default=5.0, help="Audio duration in seconds")
    parser.add_argument("--iterations", type=int, default=3, help="Number of iterations")
    parser.add_argument("--sample-rate", type=int, default=44100, help="Sample rate")
    args = parser.parse_args()

    if stems_pb2 is None:
        print("ERROR: Proto files not generated")
        sys.exit(1)

    channel = create_channel(args.host, args.port)
    if channel is None:
        print(f"Cannot connect to {args.host}:{args.port}")
        sys.exit(1)

    print(f"Benchmarking server at {args.host}:{args.port}")
    print(f"Audio: {args.duration}s @ {args.sample_rate}Hz stereo")
    print(f"Iterations: {args.iterations}")
    print()

    num_samples = int(args.duration * args.sample_rate)
    audio_data = np.random.randn(2, num_samples).astype(np.float32)

    stub = stems_pb2_grpc.StemsInferenceStub(channel)

    times = []
    for i in range(args.iterations):
        request = stems_pb2.InferenceRequest(
            session_id=i,
            input_names=["audio"],
            inputs=[
                stems_pb2.Tensor(
                    shape=stems_pb2.TensorShape(dims=list(audio_data.shape)),
                    dtype=1,
                    data=audio_data.tobytes(),
                )
            ],
            output_names=["drums", "bass", "other", "vocals"],
        )

        start = time.perf_counter()
        try:
            response = stub.RunInference(request, timeout=120.0)
            elapsed = time.perf_counter() - start

            if response.status == 0:
                times.append(elapsed)
                rtf = args.duration / elapsed
                print(f"  Iteration {i + 1}: {elapsed:.2f}s (RTF: {rtf:.2f}x)")
            else:
                print(f"  Iteration {i + 1}: FAILED - {response.error_message}")
        except grpc.RpcError as e:
            print(f"  Iteration {i + 1}: ERROR - {e.details()}")

    channel.close()

    if times:
        avg = sum(times) / len(times)
        rtf = args.duration / avg
        print()
        print(f"Results:")
        print(f"  Average: {avg:.2f}s")
        print(f"  Real-time factor: {rtf:.2f}x")
        print(f"  {'REAL-TIME CAPABLE' if rtf >= 1.0 else 'NOT REAL-TIME'}")
    else:
        print("No successful iterations")
        sys.exit(1)


if __name__ == "__main__":
    health_check()
