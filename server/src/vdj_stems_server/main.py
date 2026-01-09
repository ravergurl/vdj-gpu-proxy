import argparse
import signal
import sys
import logging
import time
import threading
from .grpc_server import serve


def main():
    parser = argparse.ArgumentParser(description="VDJ Stems GPU Server")
    parser.add_argument("--host", default="0.0.0.0", help="Host to bind to")
    parser.add_argument("--port", type=int, default=50051, help="gRPC port to listen on")
    parser.add_argument("--http-streaming-port", type=int, default=8081, help="HTTP streaming port")
    parser.add_argument("--workers", type=int, default=10, help="Max gRPC workers")
    parser.add_argument("--model", default="htdemucs", help="Demucs model name")
    parser.add_argument("--grpc-only", action="store_true", help="Only run gRPC server")
    parser.add_argument("--http-only", action="store_true", help="Only run HTTP streaming server")
    parser.add_argument("-v", "--verbose", action="store_true", help="Enable verbose logging")

    args = parser.parse_args()

    level = logging.DEBUG if args.verbose else logging.INFO
    logging.basicConfig(level=level, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")

    logger = logging.getLogger(__name__)

    if not (0 < args.port <= 65535):
        logger.error(f"Invalid port: {args.port}")
        sys.exit(1)

    if args.workers <= 0:
        logger.error(f"Invalid workers count: {args.workers}")
        sys.exit(1)

    logger.info("Pre-loading Demucs engine...")
    try:
        from .inference import get_engine

        get_engine(model_name=args.model)
    except Exception as e:
        logger.error(f"Failed to initialize engine: {e}")
        sys.exit(1)

    grpc_server = None
    http_thread = None
    shutdown_event = False

    def handle_shutdown(signum, frame):
        nonlocal shutdown_event
        if shutdown_event:
            return
        shutdown_event = True
        logger.info("Shutting down servers (grace period: 5s)...")
        if grpc_server:
            grpc_server.stop(grace=5)

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    # Start gRPC server if not http-only
    if not args.http_only:
        grpc_server = serve(host=args.host, port=args.port, max_workers=args.workers)
        logger.info(f"gRPC server running on {args.host}:{args.port}")

    # Start HTTP streaming server if not grpc-only
    if not args.grpc_only:
        from .http_streaming import run_streaming_server

        http_thread = threading.Thread(
            target=run_streaming_server,
            args=(args.host, args.http_streaming_port),
            daemon=True
        )
        http_thread.start()
        logger.info(f"HTTP streaming server running on {args.host}:{args.http_streaming_port}")

    # Wait for gRPC server if running, otherwise keep main thread alive
    if grpc_server:
        grpc_server.wait_for_termination()
    else:
        # Keep main thread alive for HTTP-only mode
        try:
            while not shutdown_event:
                time.sleep(1)
        except KeyboardInterrupt:
            pass


if __name__ == "__main__":
    main()
