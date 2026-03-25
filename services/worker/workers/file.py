import logging

from common.broker import Broker

logger = logging.getLogger(__name__)


async def process(broker: Broker, group: str, consumer: str, *, stream: str) -> None:
    await broker.setup_group(stream, group)
    print(f"Worker {consumer} is ready and waiting for files...")

    while True:
        messages = await broker.listen_for_tasks(stream, group, consumer)

        for _stream, entries in messages:
            for msg_id, data in entries:
                file_id = data["file_id"]
                text = bytes.fromhex(data["data"]).decode("utf-8", errors="replace")

                words_in_this_chunk = len(text.split())

                wc_key = f"file_wc:{file_id}"
                proc_key = f"file_proc:{file_id}"
                total_key = f"file_total:{file_id}"

                current_word_total = await broker.redis.incrby(wc_key, words_in_this_chunk)
                chunks_processed = await broker.redis.incr(proc_key)

                if data.get("is_last") == "1":
                    total_expected = data["total_chunks"]
                    await broker.redis.set(total_key, total_expected)

                total_expected_str = await broker.redis.get(total_key)

                if total_expected_str and chunks_processed >= int(total_expected_str):
                    logger.info(f"File {file_id} complete. Total words: {current_word_total}")

                    await broker.send_result(file_id, {"word_count": current_word_total})
                    await broker.redis.delete(wc_key, proc_key, total_key)

                await broker.acknowledge(stream, group, msg_id)
