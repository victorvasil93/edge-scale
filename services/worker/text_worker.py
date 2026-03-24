"""Text worker — consumes from text_tasks, calculates word count, publishes result."""

from __future__ import annotations

import logging

from common.broker import Broker

logger = logging.getLogger(__name__)

STREAM = "text_tasks"


async def process(broker: Broker, group: str, consumer: str) -> None:
    await broker.ensure_consumer_group(STREAM, group)
    logger.info("text_worker_ready", extra={"consumer": consumer})

    while True:
        messages = await broker.consume(STREAM, group, consumer, count=10)
        if not messages:
            continue

        for _stream_name, entries in messages:
            for msg_id, data in entries:
                request_id = data["request_id"]
                text = data["text"]
                word_count = len(text.split())

                await broker.publish_result(
                    request_id, {"word_count": word_count}
                )
                await broker.ack(STREAM, group, msg_id)

                logger.info(
                    "text_task_done",
                    extra={
                        "request_id": request_id,
                        "word_count": word_count,
                        "consumer": consumer,
                    },
                )
