"""
Service A — Ingestion Service

Bootstraps the gRPC server and wires the servicer to the broker.
"""

from __future__ import annotations

import asyncio
import signal
import sys
from pathlib import Path

_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from grpc import aio as grpc_aio

import edgescale_pb2_grpc
from common.broker import Broker
from common.logging import setup_logging, get_logger
from config import IngestionConfig
from servicer import EdgeScaleServicer

logger = get_logger(__name__)


async def run() -> None:
    cfg = IngestionConfig()
    setup_logging(cfg.LOG_LEVEL)

    broker = Broker(
        cfg.REDIS_URL,
        max_stream_length=cfg.MAX_STREAM_LENGTH,
        consumer_block_ms=cfg.CONSUMER_BLOCK_MS,
    )
    await broker.connect()

    server = grpc_aio.server(
        options=[
            ("grpc.max_receive_message_length", 50 * 1024 * 1024),
            ("grpc.max_send_message_length", 50 * 1024 * 1024),
            ("grpc.keepalive_time_ms", 30_000),
            ("grpc.keepalive_permit_without_calls", 1),
        ],
    )
    edgescale_pb2_grpc.add_EdgeScaleServiceServicer_to_server(
        EdgeScaleServicer(broker, cfg), server
    )

    addr = f"0.0.0.0:{cfg.GRPC_PORT}"
    server.add_insecure_port(addr)
    logger.info("ingestion_starting", extra={"addr": addr})
    await server.start()

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    await stop.wait()
    logger.info("ingestion_shutting_down")
    await server.stop(grace=5)
    await broker.close()


if __name__ == "__main__":
    asyncio.run(run())
