"""
Service B — Worker Pool

Launches concurrent text and file workers that consume from Redis Streams
using consumer groups for load distribution.
"""

from __future__ import annotations

import asyncio
import os
import signal
import sys
import uuid
from pathlib import Path

_here = Path(__file__).resolve().parent
sys.path.insert(0, str(_here))
sys.path.insert(0, str(_here.parent.parent))

from common.broker import Broker
from common.observability import setup_logging, get_logger
from config import WorkerConfig

from workers.text import process as text_process
from workers.file import process as file_process

logger = get_logger(__name__)


async def run() -> None:
    cfg = WorkerConfig()
    setup_logging(cfg.LOG_LEVEL)

    broker = Broker(
        cfg.REDIS_URL,
        max_stream_length=cfg.MAX_STREAM_LENGTH,
        consumer_block_ms=cfg.CONSUMER_BLOCK_MS,
    )
    await broker.connect()

    group = cfg.WORKER_CONSUMER_GROUP
    instance = os.getenv("HOSTNAME", uuid.uuid4().hex[:8])
    concurrency = cfg.WORKER_CONCURRENCY

    tasks: list[asyncio.Task] = []

    for i in range(concurrency):
        tasks.append(
            asyncio.create_task(
                text_process(broker, group, f"text-{instance}-{i}"),
                name=f"text-{i}",
            )
        )
        tasks.append(
            asyncio.create_task(
                file_process(broker, group, f"file-{instance}-{i}"),
                name=f"file-{i}",
            )
        )

    logger.info(
        "worker_pool_started",
        extra={"instance": instance, "concurrency": concurrency, "total_tasks": len(tasks)},
    )

    stop = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, stop.set)

    await stop.wait()
    logger.info("worker_pool_shutting_down")

    for t in tasks:
        t.cancel()
    await asyncio.gather(*tasks, return_exceptions=True)
    await broker.close()


if __name__ == "__main__":
    asyncio.run(run())
