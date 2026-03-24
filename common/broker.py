"""
Redis Streams + Pub/Sub broker for request-response over async messaging.

Architecture:
  - Tasks are published to Redis Streams (durable, consumer-group based).
  - Results are returned via Redis Pub/Sub keyed by request_id (low-latency).
  - Backpressure: stream length is capped; publish rejects when full.
"""

from __future__ import annotations

import asyncio
import json
import logging

import redis.asyncio as aioredis

from common.config import Config

logger = logging.getLogger(__name__)

RESULT_CHANNEL_PREFIX = "result:"


class BackpressureError(Exception):
    """Raised when the broker stream is at capacity."""


class Broker:
    def __init__(self, redis_url: str):
        self._redis_url = redis_url
        self._redis: aioredis.Redis | None = None

    async def connect(self) -> None:
        self._redis = aioredis.from_url(
            self._redis_url, decode_responses=True
        )
        await self._redis.ping()
        logger.info("broker_connected", extra={"redis_url": self._redis_url})

    async def close(self) -> None:
        if self._redis:
            await self._redis.aclose()

    @property
    def redis(self) -> aioredis.Redis:
        if self._redis is None:
            raise RuntimeError("Broker not connected — call connect() first")
        return self._redis

    # ── Task Publishing (with backpressure) ──────────────────────────────

    async def publish_task(self, stream: str, data: dict) -> str:
        length = await self.redis.xlen(stream)
        if length >= Config.MAX_STREAM_LENGTH:
            logger.warning(
                "backpressure_triggered",
                extra={"stream": stream, "length": length},
            )
            raise BackpressureError(
                f"Stream '{stream}' at capacity ({length}/{Config.MAX_STREAM_LENGTH})"
            )
        msg_id = await self.redis.xadd(
            stream, data, maxlen=Config.MAX_STREAM_LENGTH
        )
        logger.debug("task_published", extra={"stream": stream, "msg_id": msg_id})
        return msg_id

    # ── Result Pub/Sub ───────────────────────────────────────────────────

    async def setup_result_listener(self, request_id: str) -> aioredis.client.PubSub:
        """Subscribe to the result channel. Must be called BEFORE publish_task."""
        channel = f"{RESULT_CHANNEL_PREFIX}{request_id}"
        pubsub = self.redis.pubsub()
        await pubsub.subscribe(channel)
        return pubsub

    async def wait_for_result(
        self, pubsub: aioredis.client.PubSub, timeout: float = 30.0
    ) -> dict:
        """Block until a result message arrives on an already-subscribed channel."""
        try:
            return await asyncio.wait_for(
                self._listen(pubsub), timeout=timeout
            )
        finally:
            await pubsub.unsubscribe()
            await pubsub.aclose()

    async def cleanup_listener(self, pubsub: aioredis.client.PubSub) -> None:
        await pubsub.unsubscribe()
        await pubsub.aclose()

    async def publish_result(self, request_id: str, result: dict) -> None:
        channel = f"{RESULT_CHANNEL_PREFIX}{request_id}"
        await self.redis.publish(channel, json.dumps(result))
        logger.debug("result_published", extra={"request_id": request_id})

    # ── Consumer Groups ──────────────────────────────────────────────────

    async def ensure_consumer_group(self, stream: str, group: str) -> None:
        try:
            await self.redis.xgroup_create(stream, group, id="0", mkstream=True)
            logger.info(
                "consumer_group_created",
                extra={"stream": stream, "group": group},
            )
        except aioredis.ResponseError as exc:
            if "BUSYGROUP" not in str(exc):
                raise

    async def consume(
        self,
        stream: str,
        group: str,
        consumer: str,
        count: int = 10,
    ) -> list:
        return await self.redis.xreadgroup(
            group,
            consumer,
            {stream: ">"},
            count=count,
            block=Config.CONSUMER_BLOCK_MS,
        )

    async def ack(self, stream: str, group: str, msg_id: str) -> None:
        await self.redis.xack(stream, group, msg_id)

    # ── Private ──────────────────────────────────────────────────────────

    @staticmethod
    async def _listen(pubsub: aioredis.client.PubSub) -> dict:
        async for message in pubsub.listen():
            if message["type"] == "message":
                return json.loads(message["data"])
