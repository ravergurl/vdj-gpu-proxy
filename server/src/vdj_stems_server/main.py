import argparse
import signal
import sys
import logging
import time
from .grpc_server import serve


def main():
    parser = argparse.ArgumentParser(description="VDJ Stems GPU Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=50051, help="Port to listen on")
    parser.add_argument("--workers", type=int, default=10, help="Max gRPC workers")
    parser.add_argument("--model", default="htdemucs", help="Demucs model name")
    parser.add_argument(
        "-v", "--verbose", action="store_true", help="Enable verbose logging"
    )

    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(
        level=level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
    )

    server = serve(host=args.host, port=args.port, max_workers=args.workers)

    def handle_shutdown(signum, frame):
        print("\nStopping server...")
        server.stop(0)
        sys.exit(0)

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    print(f"VDJ Stems GPU Server running on {args.host}:{args.port}")
    try:
        while True:
            time.sleep(86400)
    except KeyboardInterrupt:
        server.stop(0)


if __name__ == "__main__":
    main()
