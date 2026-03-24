"""gRPC servicer — implements the EdgeScaleService RPC handlers."""

from __future__ import annotations

import asyncio
import base64
import uuid

import grpc

import edgescale_pb2
import edgescale_pb2_grpc
from common.broker import Broker, BackpressureError
from common.logging import get_logger
from config import IngestionConfig

logger = get_logger(__name__)


class EdgeScaleServicer(edgescale_pb2_grpc.EdgeScaleServiceServicer):
    def __init__(self, broker: Broker, cfg: IngestionConfig):
        self.broker = broker
        self.cfg = cfg

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
                pubsub, timeout=self.cfg.RESULT_TIMEOUT
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
                pubsub, timeout=self.cfg.FILE_RESULT_TIMEOUT
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
