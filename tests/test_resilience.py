"""
Resilience tests — validates system behaviour under stress and failure
conditions: backpressure, timeouts, and sustained load.

Run with:  pytest tests/test_resilience.py -v  (services must be up)
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


def _random_text(n: int) -> str:
    return " ".join(
        "".join(random.choices(string.ascii_lowercase, k=5)) for _ in range(n)
    )


@pytest.fixture(scope="module")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="module")
async def stub():
    from conftest import _ensure_proto_stubs

    _ensure_proto_stubs()
    import edgescale_pb2_grpc

    channel = grpc.aio.insecure_channel(GRPC_TARGET)
    yield edgescale_pb2_grpc.EdgeScaleServiceStub(channel)
    await channel.close()


@pytest.mark.asyncio
async def test_sustained_load(stub):
    """Send a sustained burst of requests and verify all succeed or gracefully reject."""
    import edgescale_pb2

    total = 200
    success = 0
    rejected = 0
    errors = 0

    async def _send(i: int):
        nonlocal success, rejected, errors
        try:
            resp = await stub.AnalyzeText(
                edgescale_pb2.AnalyzeTextRequest(text=_random_text(50))
            )
            if resp.word_count > 0:
                success += 1
        except grpc.RpcError as exc:
            if exc.code() == grpc.StatusCode.RESOURCE_EXHAUSTED:
                rejected += 1
            else:
                errors += 1

    await asyncio.gather(*[_send(i) for i in range(total)])

    print(f"\n  Sustained load: {success} ok, {rejected} rejected (backpressure), {errors} errors")
    assert errors == 0, f"Unexpected errors: {errors}"
    assert success + rejected == total


@pytest.mark.asyncio
async def test_large_text_payload(stub):
    """Ensure very large text payloads are processed correctly."""
    import edgescale_pb2

    big_text = _random_text(100_000)
    expected = 100_000

    resp = await stub.AnalyzeText(
        edgescale_pb2.AnalyzeTextRequest(text=big_text)
    )
    assert resp.word_count == expected


@pytest.mark.asyncio
async def test_empty_text(stub):
    """Empty text should return word_count=0."""
    import edgescale_pb2

    resp = await stub.AnalyzeText(edgescale_pb2.AnalyzeTextRequest(text=""))
    assert resp.word_count == 0


@pytest.mark.asyncio
async def test_rapid_heartbeats(stub):
    """Fire 500 heartbeats as fast as possible — none should fail."""
    import edgescale_pb2

    count = 500

    async def _beat(i: int):
        await stub.Heartbeat(
            edgescale_pb2.HeartbeatRequest(
                agent_id=f"stress-{i}", timestamp=int(time.time())
            )
        )

    t0 = time.monotonic()
    await asyncio.gather(*[_beat(i) for i in range(count)])
    elapsed = time.monotonic() - t0
    print(f"\n  {count} rapid heartbeats in {elapsed:.2f}s ({count/elapsed:.0f}/s)")
