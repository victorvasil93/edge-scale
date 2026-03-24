"""
File worker — consumes file chunks from file_tasks, maintains a running word
count per file_id using atomic Redis operations (Lua script), and publishes
the final result once all chunks have been processed.
"""

from __future__ import annotations

import base64
import logging

from common.broker import Broker

logger = logging.getLogger(__name__)

STREAM = "file_tasks"

# Lua script for atomic chunk accounting.
# Returns the final word_count (>= 0) when the file is complete, else -1.
_LUA_PROCESS_CHUNK = """
local wc_key   = KEYS[1]
local proc_key  = KEYS[2]
local total_key = KEYS[3]

local chunk_words  = tonumber(ARGV[1])
local is_last      = ARGV[2] == "1"
local total_chunks = tonumber(ARGV[3])

redis.call('INCRBY', wc_key, chunk_words)
local processed = redis.call('INCRBY', proc_key, 1)

if is_last then
    redis.call('SET', total_key, tostring(total_chunks))
end

local total = redis.call('GET', total_key)
if total ~= false and processed >= tonumber(total) then
    local final_wc = tonumber(redis.call('GET', wc_key))
    redis.call('DEL', wc_key, proc_key, total_key)
    return final_wc
end

return -1
"""


async def process(broker: Broker, group: str, consumer: str) -> None:
    await broker.ensure_consumer_group(STREAM, group)

    script_sha = await broker.redis.script_load(_LUA_PROCESS_CHUNK)
    logger.info("file_worker_ready", extra={"consumer": consumer})

    while True:
        messages = await broker.consume(STREAM, group, consumer, count=10)
        if not messages:
            continue

        for _stream_name, entries in messages:
            for msg_id, data in entries:
                file_id = data["file_id"]
                chunk_data = base64.b64decode(data["data"])
                is_last = data["is_last"] == "1"
                total_chunks = int(data.get("total_chunks", "0"))

                text = chunk_data.decode("utf-8", errors="ignore")
                chunk_words = len(text.split())

                result = await broker.redis.evalsha(
                    script_sha,
                    3,
                    f"file_wc:{file_id}",
                    f"file_proc:{file_id}",
                    f"file_total:{file_id}",
                    str(chunk_words),
                    "1" if is_last else "0",
                    str(total_chunks),
                )

                await broker.ack(STREAM, group, msg_id)

                if int(result) >= 0:
                    word_count = int(result)
                    await broker.publish_result(
                        file_id, {"word_count": word_count, "file_id": file_id}
                    )
                    logger.info(
                        "file_task_done",
                        extra={
                            "file_id": file_id,
                            "word_count": word_count,
                            "consumer": consumer,
                        },
                    )
                else:
                    logger.debug(
                        "file_chunk_processed",
                        extra={
                            "file_id": file_id,
                            "chunk_index": data["chunk_index"],
                            "consumer": consumer,
                        },
                    )
