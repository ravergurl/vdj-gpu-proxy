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
    result = subprocess.run(cmd, capture_output=True, text=True)

    if result.returncode != 0:
        print(f"Proto generation failed:\n{result.stderr}")
        sys.exit(1)

    grpc_file = output_dir / "stems_pb2_grpc.py"
    if grpc_file.exists():
        try:
            content = grpc_file.read_text(encoding="utf-8")
            new_content = content.replace("import stems_pb2", "from . import stems_pb2")
            if content == new_content:
                print(f"Warning: No import replacements made in {grpc_file}")
            grpc_file.write_text(new_content, encoding="utf-8")
        except Exception as e:
            print(f"Error fixing imports in {grpc_file}: {e}")
            sys.exit(1)

    print("Proto generation complete!")


if __name__ == "__main__":
    main()
