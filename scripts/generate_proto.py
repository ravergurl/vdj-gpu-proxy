#!/usr/bin/env python3
"""Generate Python protobuf/gRPC code from stems.proto."""

import subprocess
import sys
from pathlib import Path


def main():
    root = Path(__file__).parent.parent
    proto_dir = root / "proto"
    output_dir = root / "server" / "src" / "vdj_stems_server"

    proto_file = proto_dir / "stems.proto"

    if not proto_file.exists():
        print(f"Error: {proto_file} not found")
        sys.exit(1)

    output_dir.mkdir(parents=True, exist_ok=True)

    # Generate protobuf
    cmd = [
        sys.executable,
        "-m",
        "grpc_tools.protoc",
        f"-I{proto_dir}",
        f"--python_out={output_dir}",
        f"--grpc_python_out={output_dir}",
        f"--pyi_out={output_dir}",
        str(proto_file),
    ]

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd)

    if result.returncode != 0:
        print("Proto generation failed")
        sys.exit(1)

    # Fix imports in generated files
    grpc_file = output_dir / "stems_pb2_grpc.py"
    if grpc_file.exists():
        content = grpc_file.read_text()
        content = content.replace("import stems_pb2", "from . import stems_pb2")
        grpc_file.write_text(content)

    print("Proto generation complete!")


if __name__ == "__main__":
    main()
