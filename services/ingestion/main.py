"""
Service A — Ingestion Service

gRPC server that accepts heartbeats, text-analysis requests, and streaming
file uploads from edge agents.  Tasks are offloaded to a Redis Streams broker
and the service waits for the worker result via Pub/Sub before responding.
"""

from __future__ import annotations

import asyncio
import base64
import signal
import sys
import uuid
from pathlib import Path

# Resolve project root so imports work from any working directory
sys.path.insert(0, str(Path(__file__).resolve().parent.parent.parent))

import grpc
from grpc import aio as grpc_aio

import edgescale_pb2
import edgescale_pb2_grpc
from common.broker import Broker, BackpressureError
from common.config import Config
from common.observability import setup_logging, get_logger

logger = get_logger(__name__)


class EdgeScaleServicer(edgescale_pb2_grpc.EdgeScaleServiceServicer):
    def __init__(self, broker: Broker):
        self.broker = broker

    # ── Heartbeat (fire-and-forget) ──────────────────────────────────────

    async def Heartbeat(self, request, context):
        logger.info(
            "heartbeat",
            extra={"agent_id": request.agent_id, "ts": request.timestamp},
        )
        return edgescale_pb2.HeartbeatResponse()

    # ── Text Analysis (request-response over async broker) ───────────────

    async def AnalyzeText(self, request, context):
        request_id = str(uuid.uuid4())
        logger.info(
            "analyze_text_start",
            extra={"request_id": request_id, "text_len": len(request.text)},
        )

        pubsub = await self.broker.setup_result_listener(request_id)

        try:
            await self.broker.publish_task(
                "text_tasks",
                {"request_id": request_id, "text": request.text},
            )
        except BackpressureError:
            await self.broker.cleanup_listener(pubsub)
            context.set_code(grpc.StatusCode.RESOURCE_EXHAUSTED)
            context.set_details("System under heavy load — retry with backoff")
            return edgescale_pb2.AnalyzeTextResponse()

        try:
            result = await self.broker.wait_for_result(
                pubsub, timeout=Config.RESULT_TIMEOUT
            )
            logger.info(
                "analyze_text_done",
                extra={"request_id": request_id, "word_count": result["word_count"]},
            )
            return edgescale_pb2.AnalyzeTextResponse(
                request_id=request_id, word_count=result["word_count"]
            )
        except asyncio.TimeoutError:
            logger.warning("analyze_text_timeout", extra={"request_id": request_id})
            context.set_code(grpc.StatusCode.DEADLINE_EXCEEDED)
            context.set_details("Processing timeout")
            return edgescale_pb2.AnalyzeTextResponse()

    # ── File Upload (client-streaming → broker → worker → pub/sub) ───────

    async def UploadAndAnalyzeFile(self, request_iterator, context):
        file_id = str(uuid.uuid4())
        logger.info("file_upload_start", extra={"file_id": file_id})

        pubsub = await self.broker.setup_result_listener(file_id)

        chunk_count = 0
        total_bytes = 0

        try:
            async for chunk in request_iterator:
                total_bytes += len(chunk.data)
                await self.broker.publish_task(
                    "file_tasks",
                    {
                        "file_id": file_id,
                        "data": base64.b64encode(chunk.data).decode(),
                        "chunk_index": str(chunk.chunk_index),
                        "is_last": "1" if chunk.is_last else "0",
                        "total_chunks": str(chunk.chunk_index + 1)
                        if chunk.is_last
                        else "0",
                    },
                )
                chunk_count += 1
        except BackpressureError:
            await self.broker.cleanup_listener(pubsub)
            context.set_code(grpc.StatusCode.RESOURCE_EXHAUSTED)
            context.set_details("System under heavy load — retry with backoff")
            return edgescale_pb2.FileAnalysisResponse()

        logger.info(
            "file_upload_done",
            extra={
                "file_id": file_id,
                "chunks": chunk_count,
                "bytes": total_bytes,
            },
        )

        try:
            result = await self.broker.wait_for_result(
                pubsub, timeout=Config.FILE_RESULT_TIMEOUT
            )
            logger.info(
                "file_analysis_done",
                extra={"file_id": file_id, "word_count": result["word_count"]},
            )
            return edgescale_pb2.FileAnalysisResponse(
                file_id=file_id, word_count=result["word_count"]
            )
        except asyncio.TimeoutError:
            logger.warning("file_analysis_timeout", extra={"file_id": file_id})
            context.set_code(grpc.StatusCode.DEADLINE_EXCEEDED)
            context.set_details("Processing timeout")
            return edgescale_pb2.FileAnalysisResponse()


# ── Server bootstrap ─────────────────────────────────────────────────────

async def serve() -> None:
    setup_logging()
    broker = Broker(Config.REDIS_URL)
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
        EdgeScaleServicer(broker), server
    )

    addr = f"0.0.0.0:{Config.GRPC_PORT}"
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
    asyncio.run(serve())
