"""Shared fixtures for EdgeScale integration tests."""

from __future__ import annotations

import os
import subprocess
import sys

import pytest

GRPC_HOST = os.getenv("GRPC_HOST", "localhost")
GRPC_PORT = os.getenv("GRPC_PORT", "50051")
GRPC_TARGET = f"{GRPC_HOST}:{GRPC_PORT}"

PROTO_DIR = os.path.join(os.path.dirname(__file__), "..", "proto")
GEN_DIR = os.path.dirname(__file__)


def _ensure_proto_stubs() -> None:
    pb2 = os.path.join(GEN_DIR, "edgescale_pb2.py")
    if os.path.exists(pb2):
        return
    subprocess.check_call(
        [
            sys.executable,
            "-m",
            "grpc_tools.protoc",
            f"-I{PROTO_DIR}",
            f"--python_out={GEN_DIR}",
            f"--grpc_python_out={GEN_DIR}",
            os.path.join(PROTO_DIR, "edgescale.proto"),
        ]
    )


_ensure_proto_stubs()
sys.path.insert(0, GEN_DIR)

import edgescale_pb2 as pb2  # noqa: E402
import edgescale_pb2_grpc as pb2_grpc  # noqa: E402


@pytest.fixture(scope="session")
def grpc_target() -> str:
    return GRPC_TARGET


@pytest.fixture(scope="session")
def pb():
    return pb2


@pytest.fixture(scope="session")
def pb_grpc():
    return pb2_grpc
