#!/usr/bin/env bash
set -euo pipefail

ROOT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)
PROTO_DIR="${ROOT_DIR}/proto"
OUT_DIR="${ROOT_DIR}/src/microservice_template/proto"

mkdir -p "${OUT_DIR}"
uv run python -m grpc_tools.protoc \
  --proto_path="${PROTO_DIR}" \
  --python_out="${OUT_DIR}" \
  --grpc_python_out="${OUT_DIR}" \
  "${PROTO_DIR}/greeter.proto"

echo "Generated gRPC stubs into ${OUT_DIR}" >&2
