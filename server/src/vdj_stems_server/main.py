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

    server = serve(host=args.host, port=args.port, max_workers=args.workers)
    shutdown_event = False

    def handle_shutdown(signum, frame):
        nonlocal shutdown_event
        if shutdown_event:
            return
        shutdown_event = True
        logger.info("Shutting down server (grace period: 5s)...")
        server.stop(grace=5)

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    logger.info(f"VDJ Stems GPU Server running on {args.host}:{args.port}")
    server.wait_for_termination()


if __name__ == "__main__":
    main()
