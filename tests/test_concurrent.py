"""
Integration tests — simulates concurrent edge agents sending heartbeats,
text analysis requests, and file uploads through the gRPC ingestion service.

Run with:  pytest tests/ -v  (services must be up via docker compose)
"""

from __future__ import annotations

import asyncio
import os
import random
import string
import time

import grpc
import pytest

GRPC_TARGET = os.getenv("GRPC_TARGET", "localhost:50051")
NUM_HEARTBEATS = 100
NUM_TEXT_REQUESTS = 50
NUM_FILE_UPLOADS = 10
FILE_CHUNK_SIZE = 64 * 1024  # 64 KB


def _random_text(word_count: int) -> str:
    return " ".join(
        "".join(random.choices(string.ascii_lowercase, k=random.randint(3, 10)))
        for _ in range(word_count)
    )


def _random_file(size_bytes: int) -> bytes:
    words = []
    current = 0
    while current < size_bytes:
        word = "".join(random.choices(string.ascii_lowercase, k=random.randint(3, 12)))
        words.append(word)
        current += len(word) + 1
    return " ".join(words).encode("utf-8")[:size_bytes]


@pytest.fixture(scope="session")
async def stub():
    from conftest import _ensure_proto_stubs

    _ensure_proto_stubs()
    import edgescale_pb2_grpc

    channel = grpc.aio.insecure_channel(
        GRPC_TARGET,
        options=[
            ("grpc.max_receive_message_length", 50 * 1024 * 1024),
            ("grpc.max_send_message_length", 50 * 1024 * 1024),
        ],
    )
    yield edgescale_pb2_grpc.EdgeScaleServiceStub(channel)
    await channel.close()


# ── Heartbeat tests ──────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_concurrent_heartbeats(stub):
    import edgescale_pb2

    async def _beat(i: int):
        await stub.Heartbeat(
            edgescale_pb2.HeartbeatRequest(
                agent_id=f"agent-{i:04d}", timestamp=int(time.time())
            )
        )

    t0 = time.monotonic()
    await asyncio.gather(*[_beat(i) for i in range(NUM_HEARTBEATS)])
    elapsed = time.monotonic() - t0

    print(f"\n  {NUM_HEARTBEATS} heartbeats in {elapsed:.2f}s ({NUM_HEARTBEATS/elapsed:.0f} req/s)")


# ── Text Analysis tests ─────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_concurrent_text_analysis(stub):
    import edgescale_pb2

    texts = [_random_text(random.randint(10, 500)) for _ in range(NUM_TEXT_REQUESTS)]
    expected_counts = [len(t.split()) for t in texts]

    async def _analyze(idx: int):
        resp = await stub.AnalyzeText(
            edgescale_pb2.AnalyzeTextRequest(text=texts[idx])
        )
        return resp.word_count

    t0 = time.monotonic()
    results = await asyncio.gather(*[_analyze(i) for i in range(NUM_TEXT_REQUESTS)])
    elapsed = time.monotonic() - t0

    for i, (got, want) in enumerate(zip(results, expected_counts)):
        assert got == want, f"Text #{i}: expected {want}, got {got}"

    print(f"\n  {NUM_TEXT_REQUESTS} text analyses in {elapsed:.2f}s ({NUM_TEXT_REQUESTS/elapsed:.0f} req/s)")


# ── File Upload tests ────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_concurrent_file_uploads(stub):
    import edgescale_pb2

    file_sizes = [random.randint(100_000, 1_000_000) for _ in range(NUM_FILE_UPLOADS)]
    files = [_random_file(s) for s in file_sizes]
    expected = [len(f.decode("utf-8").split()) for f in files]

    async def _upload(idx: int):
        data = files[idx]

        async def _chunks():
            import uuid as _uuid

            fid = str(_uuid.uuid4())
            offset = 0
            chunk_idx = 0
            while offset < len(data):
                end = min(offset + FILE_CHUNK_SIZE, len(data))
                is_last = end >= len(data)
                yield edgescale_pb2.FileChunk(
                    file_id=fid,
                    data=data[offset:end],
                    chunk_index=chunk_idx,
                    is_last=is_last,
                    filename=f"test-{idx}.txt",
                )
                offset = end
                chunk_idx += 1

        resp = await stub.UploadAndAnalyzeFile(_chunks())
        return resp.word_count

    t0 = time.monotonic()
    results = await asyncio.gather(*[_upload(i) for i in range(NUM_FILE_UPLOADS)])
    elapsed = time.monotonic() - t0

    for i, (got, want) in enumerate(zip(results, expected)):
        assert got == want, f"File #{i}: expected {want}, got {got}"

    print(f"\n  {NUM_FILE_UPLOADS} file uploads in {elapsed:.2f}s ({NUM_FILE_UPLOADS/elapsed:.0f} req/s)")
