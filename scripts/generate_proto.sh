#!/usr/bin/env bash
set -euo pipefail

PROTO_DIR="$(cd "$(dirname "$0")/../proto" && pwd)"
OUT_DIR="$(cd "$(dirname "$0")/.." && pwd)"

echo "Generating Python gRPC stubs from ${PROTO_DIR}/edgescale.proto ..."

python -m grpc_tools.protoc \
    "-I${PROTO_DIR}" \
    "--python_out=${OUT_DIR}" \
    "--grpc_python_out=${OUT_DIR}" \
    "--pyi_out=${OUT_DIR}" \
    "${PROTO_DIR}/edgescale.proto"

echo "Generated:"
ls -la "${OUT_DIR}"/edgescale_pb2*.py*
