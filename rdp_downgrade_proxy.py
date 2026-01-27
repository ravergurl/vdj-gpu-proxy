import socket
import threading
import time

RDP_INTERCEPTOR_PORT = 13389
CLOUDFLARED_RDP_PORT = 15389


def forward(src, dst):
    try:
        while True:
            data = src.recv(4096)
            if not data:
                break
            dst.sendall(data)
    except:
        pass
    finally:
        src.close()
        dst.close()


def handle_client(client_socket):
    try:
        server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        server_socket.connect(("127.0.0.1", CLOUDFLARED_RDP_PORT))

        data = client_socket.recv(4096)
        # Check for RDP negotiation request structure
        # Standard RDP negotiation starts with 0x03 0x00
        if len(data) > 7 and data[0] == 0x03:
            print(f"Intercepted RDP handshake ({len(data)} bytes)")
            # Standard RDP Security: 0x00000000
            # NLA (CredSSP): 0x00000002
            # TLS: 0x00000001
            # Look for requestedProtocols field (usually at index 7 for RDP_NEG_REQ)
            if data[4] == (len(data) - 4) and data[5] == 0xE0:
                # Potential RDP_NEG_REQ
                # Attempt to overwrite flags to 0x00000000 (Standard Security)
                # This depends on the exact packet structure, but common location is end of packet
                modified_data = bytearray(data)
                # Find protocol flags pattern 0x01 0x00 0x08 0x00 (RDP_NEG_DATA)
                neg_idx = modified_data.find(b"\x01\x00\x08\x00")
                if neg_idx != -1:
                    print("Found protocol flags. Downgrading...")
                    modified_data[neg_idx + 4 : neg_idx + 8] = b"\x00\x00\x00\x00"
                    data = bytes(modified_data)

        server_socket.sendall(data)

        threading.Thread(
            target=forward, args=(client_socket, server_socket), daemon=True
        ).start()
        threading.Thread(
            target=forward, args=(server_socket, client_socket), daemon=True
        ).start()
    except Exception as e:
        print(f"Proxy Error: {e}")
        client_socket.close()


def run_downgrade_proxy():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind(("127.0.0.1", RDP_INTERCEPTOR_PORT))
    server.listen(5)
    print(
        f"RDP Interceptor listening on 127.0.0.1:{RDP_INTERCEPTOR_PORT} (Target: {CLOUDFLARED_RDP_PORT})"
    )

    while True:
        client, addr = server.accept()
        threading.Thread(target=handle_client, args=(client,), daemon=True).start()


if __name__ == "__main__":
    run_downgrade_proxy()
