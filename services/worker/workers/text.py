import logging

from common.broker import Broker

logger = logging.getLogger(__name__)


async def process(broker: Broker, group: str, consumer: str, *, stream: str) -> None:
    await broker.setup_group(stream, group)
    logger.info("text_worker_ready", extra={"consumer": consumer})

    while True:
        messages = await broker.listen_for_tasks(stream, group, consumer)
        if not messages:
            continue

        for _stream_name, entries in messages:
            for msg_id, data in entries:
                request_id = data["request_id"]
                text = data["text"]
                word_count = len(text.split())

                await broker.send_result(
                    request_id, {"word_count": word_count}
                )
                await broker.acknowledge(stream, group, msg_id)

                logger.info(
                    "text_task_done",
                    extra={
                        "request_id": request_id,
                        "word_count": word_count,
                        "consumer": consumer,
                    },
                )
