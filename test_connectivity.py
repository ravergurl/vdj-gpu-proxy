import grpc
import sys
from vdj_stems_server import stems_pb2
from vdj_stems_server import stems_pb2_grpc


def test_connection(url):
    print(f"Connecting to {url}...")
    # Cloudflare tunnels use HTTPS
    target = url.replace("https://", "")
    if ":" not in target:
        target += ":443"

    creds = grpc.ssl_channel_credentials()
    options = [("grpc.ssl_target_name_override", target.split(":")[0])]

    channel = grpc.secure_channel(target, creds, options=options)
    stub = stems_pb2_grpc.StemsInferenceStub(channel)

    try:
        response = stub.GetServerInfo(stems_pb2.Empty(), timeout=10)
        print(f"Success! Server version: {response.version}")
        print(f"Ready: {response.ready}")
        return True
    except grpc.RpcError as e:
        print(f"Failed to connect: {e.code()} - {e.details()}")
        return False


if __name__ == "__main__":
    url = "https://programming-msgstr-need-resolved.trycloudflare.com"
    test_connection(url)
