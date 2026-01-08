import grpc
import numpy as np
import io
from vdj_stems_server import stems_pb2
from vdj_stems_server import stems_pb2_grpc


def run_test():
    print("Connecting to local server...")
    channel = grpc.insecure_channel("127.0.0.1:50051")
    stub = stems_pb2_grpc.StemsInferenceStub(channel)

    # 1. Check Server Info
    print("Checking Server Info...")
    info = stub.GetServerInfo(stems_pb2.Empty())
    print(
        f"Server Info: version={info.version}, ready={info.ready}, model={info.model_name}"
    )

    if not info.ready:
        print("Server not ready yet. Waiting...")
        return False

    # 2. Run Inference with 1s of 44.1kHz Stereo Sine Wave
    print("Running Inference Test (1s sine wave)...")
    t = np.linspace(0, 1, 44100)
    # Stereo: (2, 44100)
    audio = np.sin(2 * np.pi * 440 * t).astype(np.float32)
    audio_stereo = np.stack([audio, audio])

    request = stems_pb2.InferenceRequest(
        session_id=123,
        input_names=["input"],
        inputs=[
            stems_pb2.Tensor(
                shape=stems_pb2.TensorShape(dims=list(audio_stereo.shape)),
                dtype=1,  # FLOAT
                data=audio_stereo.tobytes(),
            )
        ],
        output_names=["vocals", "drums", "bass", "other"],
    )

    try:
        response = stub.RunInference(request, timeout=60)
        print(f"Inference Response Status: {response.status}")
        if response.status == 0:
            print(f"Received {len(response.outputs)} output stems.")
            for output in response.outputs:
                shape = output.shape.dims
                print(f" - Stem: data_size={len(output.data)}, shape={shape}")
            return True
        else:
            print(f"Error Message: {response.error_message}")
            return False
    except grpc.RpcError as e:
        print(f"gRPC Error: {e.code()} - {e.details()}")
        return False


if __name__ == "__main__":
    if run_test():
        print("TEST PASSED")
        exit(0)
    else:
        print("TEST FAILED")
        exit(1)
