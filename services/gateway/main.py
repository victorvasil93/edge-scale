"""
REST/HTTP Gateway — translates HTTP requests from the frontend into gRPC
calls to the Ingestion Service.  Deployed alongside the backend on Scaleway;
the Vercel frontend hits this API.
"""

from __future__ import annotations

import sys
import time
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

_here = Path(__file__).resolve().parent
sys.path.insert(0, str(_here))
sys.path.insert(0, str(_here.parent.parent))

import grpc
from grpc import aio as grpc_aio
from fastapi import FastAPI, File, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel

import edgescale_pb2
import edgescale_pb2_grpc
from common.observability import setup_logging, get_logger
from config import GatewayConfig

logger = get_logger(__name__)

CHUNK_SIZE = 64 * 1024  # 64 KB


class HeartbeatPayload(BaseModel):
    agent_id: str
    metadata: dict[str, str] | None = None


class TextPayload(BaseModel):
    text: str


@asynccontextmanager
async def lifespan(app: FastAPI):
    cfg = GatewayConfig()
    setup_logging(cfg.LOG_LEVEL)
    target = f"{cfg.INGESTION_GRPC_HOST}:{cfg.INGESTION_GRPC_PORT}"
    app.state.channel = grpc_aio.insecure_channel(
        target,
        options=[
            ("grpc.max_receive_message_length", 50 * 1024 * 1024),
            ("grpc.max_send_message_length", 50 * 1024 * 1024),
        ],
    )
    app.state.stub = edgescale_pb2_grpc.EdgeScaleServiceStub(app.state.channel)
    logger.info("gateway_started", extra={"grpc_target": target})
    yield
    await app.state.channel.close()


app = FastAPI(title="EdgeScale Gateway", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _grpc_error(exc: grpc.RpcError) -> HTTPException:
    code = exc.code()
    mapping = {
        grpc.StatusCode.RESOURCE_EXHAUSTED: 429,
        grpc.StatusCode.DEADLINE_EXCEEDED: 504,
        grpc.StatusCode.UNAVAILABLE: 503,
    }
    return HTTPException(
        status_code=mapping.get(code, 500),
        detail=exc.details() or str(code),
    )


@app.get("/api/health")
async def health():
    return {"status": "ok"}


@app.post("/api/heartbeat")
async def heartbeat(payload: HeartbeatPayload):
    t0 = time.monotonic()
    try:
        await app.state.stub.Heartbeat(
            edgescale_pb2.HeartbeatRequest(
                agent_id=payload.agent_id,
                timestamp=int(time.time()),
                metadata=payload.metadata or {},
            )
        )
        elapsed = round((time.monotonic() - t0) * 1000, 1)
        return {"status": "accepted", "agent_id": payload.agent_id, "latency_ms": elapsed}
    except grpc.RpcError as exc:
        raise _grpc_error(exc)


@app.post("/api/analyze-text")
async def analyze_text(payload: TextPayload):
    t0 = time.monotonic()
    try:
        resp = await app.state.stub.AnalyzeText(
            edgescale_pb2.AnalyzeTextRequest(text=payload.text)
        )
        elapsed = round((time.monotonic() - t0) * 1000, 1)
        return {
            "request_id": resp.request_id,
            "word_count": resp.word_count,
            "latency_ms": elapsed,
        }
    except grpc.RpcError as exc:
        raise _grpc_error(exc)


@app.post("/api/upload-file")
async def upload_file(file: UploadFile = File(...)):
    t0 = time.monotonic()
    file_id = str(uuid.uuid4())

    async def _chunks():
        chunk_index = 0
        prev_data = await file.read(CHUNK_SIZE)

        while prev_data:
            next_data = await file.read(CHUNK_SIZE)
            is_last = len(next_data) == 0
            yield edgescale_pb2.FileChunk(
                file_id=file_id,
                data=prev_data,
                chunk_index=chunk_index,
                is_last=is_last,
                filename=file.filename or "unknown",
            )
            chunk_index += 1
            prev_data = next_data

    try:
        resp = await app.state.stub.UploadAndAnalyzeFile(_chunks())
        elapsed = round((time.monotonic() - t0) * 1000, 1)
        return {
            "file_id": resp.file_id,
            "word_count": resp.word_count,
            "filename": file.filename,
            "latency_ms": elapsed,
        }
    except grpc.RpcError as exc:
        raise _grpc_error(exc)


if __name__ == "__main__":
    import uvicorn

    cfg = GatewayConfig()
    uvicorn.run(
        "main:app",
        host="0.0.0.0",
        port=cfg.GATEWAY_PORT,
        log_level="info",
    )
