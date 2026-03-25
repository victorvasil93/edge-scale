import asyncio
import json
import redis.asyncio as aioredis


class Broker:
    def __init__(self, redis_url: str):
        self.url = redis_url
        self.redis = None

    async def connect(self):
        self.redis = aioredis.from_url(self.url, decode_responses=True)
        await self.redis.ping()
        print(f"Connected to Redis at {self.url}")

    async def close(self):
        if self.redis:
            await self.redis.aclose()

    # --- Task Management (Streams) ---

    async def send_task(self, stream_name: str, data: dict):
        """Pushes a task into a Redis stream."""
        return await self.redis.xadd(stream_name, data, maxlen=10000)

    async def listen_for_tasks(self, stream: str, group: str, consumer: str):
        """Basic wrapper for reading from a group."""
        return await self.redis.xreadgroup(
            groupname=group,
            consumername=consumer,
            streams={stream: ">"},
            count=1,
            block=5000
        )

    async def acknowledge(self, stream: str, group: str, message_id: str):
        """Tell Redis we've successfully handled the message."""
        await self.redis.xack(stream, group, message_id)

    # --- Results (Pub/Sub) ---

    async def subscribe_for_result(self, request_id: str):
        """Subscribe to the result channel. Must be called BEFORE send_task."""
        channel = f"result:{request_id}"
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(channel)
        return pubsub

    async def wait_for_result(self, pubsub, timeout: float = 30.0):
        """Block until a result arrives on an already-subscribed channel."""
        try:
            return await asyncio.wait_for(self._get_next_msg(pubsub), timeout)
        finally:
            await pubsub.unsubscribe()
            await pubsub.aclose()

    async def cleanup_listener(self, pubsub) -> None:
        """Clean up a subscription without waiting (for error paths)."""
        await pubsub.unsubscribe()
        await pubsub.aclose()

    async def send_result(self, request_id: str, result: dict):
        """Broadcasts the result back to whoever is listening."""
        channel = f"result:{request_id}"
        await self.redis.publish(channel, json.dumps(result))

    # --- Helpers ---

    async def setup_group(self, stream: str, group: str):
        """Ensures the consumer group exists without crashing if it does."""
        try:
            await self.redis.xgroup_create(stream, group, id="0", mkstream=True)
        except Exception:
            pass

    @staticmethod
    async def _get_next_msg(pubsub):
        """Helper to loop through pubsub messages until we get actual data."""
        async for msg in pubsub.listen():
            if msg["type"] == "message":
                return json.loads(msg["data"])
