import asyncio
import uuid
import grpc

import edgescale_pb2
import edgescale_pb2_grpc


class RPCHandler(edgescale_pb2_grpc.EdgeScaleServiceServicer):
    def __init__(self, broker, config):
        self.broker = broker
        self.config = config

    async def Heartbeat(self, request, context):
        print(f"Received heartbeat from agent: {request.agent_id}")
        return edgescale_pb2.HeartbeatResponse()

    async def AnalyzeText(self, request, context):
        job_id = str(uuid.uuid4())

        await self.broker.send_task(
            self.config.TEXT_STREAM_KEY,
            {"request_id": job_id, "text": request.text}
        )

        try:
            result = await self.broker.wait_for_result(
                request_id=job_id,
                timeout=self.config.RESULT_TIMEOUT
            )
            return edgescale_pb2.AnalyzeTextResponse(
                request_id=job_id, 
                word_count=result["word_count"]
            )
        except asyncio.TimeoutError:
            context.set_code(grpc.StatusCode.DEADLINE_EXCEEDED)
            context.set_details("The worker took too long to respond.")
            return edgescale_pb2.AnalyzeTextResponse()

    async def UploadAndAnalyzeFile(self, request_iterator, context):
        file_id = str(uuid.uuid4())
        chunk_count = 0

        async for chunk in request_iterator:
            chunk_count += 1
            payload = {
                "file_id": file_id,
                "data": chunk.data.hex(),
                "is_last": "1" if chunk.is_last else "0",
            }
            if chunk.is_last:
                payload["total_chunks"] = str(chunk_count)
            await self.broker.send_task(self.config.FILE_STREAM_KEY, payload)

        try:
            result = await self.broker.wait_for_result(
                request_id=file_id,
                timeout=self.config.FILE_RESULT_TIMEOUT
            )
            return edgescale_pb2.FileAnalysisResponse(
                file_id=file_id, 
                word_count=result["word_count"]
            )
        except asyncio.TimeoutError:
            context.set_code(grpc.StatusCode.DEADLINE_EXCEEDED)
            return edgescale_pb2.FileAnalysisResponse()
