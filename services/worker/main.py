import asyncio
import os
import uuid

from common.broker import Broker
from config import WorkerConfig

from workers.text import process as text_process
from workers.file import process as file_process


async def run():
    cfg = WorkerConfig()
    
    broker = Broker(cfg.REDIS_URL)
    await broker.connect()

    instance_id = os.getenv("HOSTNAME", uuid.uuid4().hex[:8])
    group_name = cfg.WORKER_CONSUMER_GROUP
    
    print(f"--- Starting Worker Pool [Instance: {instance_id}] ---")

    worker_tasks = []

    for i in range(cfg.WORKER_CONCURRENCY):
        text_worker = asyncio.create_task(
            text_process(broker=broker, group=group_name, consumer=f"text-{instance_id}-{i}", stream=cfg.REDIS_STREAM_KEY)
        )
        worker_tasks.append(text_worker)

        # Create a file processing worker
        file_worker = asyncio.create_task(
            file_process(broker=broker, group=group_name, consumer=f"file-{instance_id}-{i}", stream=cfg.FILE_STREAM_KEY)
        )
        worker_tasks.append(file_worker)

    print(f"Successfully launched {len(worker_tasks)} total workers.")

    try:
        await asyncio.gather(*worker_tasks)
    except asyncio.CancelledError:
        print("Workers are stopping...")

if __name__ == "__main__":
    try:
        asyncio.run(run())
    except KeyboardInterrupt:
        pass
