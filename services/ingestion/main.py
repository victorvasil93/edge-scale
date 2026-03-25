import asyncio
import sys
from pathlib import Path

# Essential path setup for local imports
_root = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(_root))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from grpc import aio as grpc_aio
import edgescale_pb2_grpc
from common.broker import Broker
from config import IngestionConfig
from rpc_handler import RPCHandler

from common.logging import get_logger

logger = get_logger(__name__)


MB_IN_BYTES = 1024 * 1024


async def run():
    cfg = IngestionConfig()
    
    broker = Broker(cfg.REDIS_URL)
    await broker.connect()

    server = grpc_aio.server(options=[
        ("grpc.max_receive_message_length", 50 * MB_IN_BYTES),
        ("grpc.keepalive_time_ms", 30_000),
    ])

    rpc_handler = RPCHandler(broker, cfg)
    edgescale_pb2_grpc.add_EdgeScaleServiceServicer_to_server(rpc_handler, server)

    server.add_insecure_port(f"0.0.0.0:{cfg.GRPC_PORT}")

    await server.start()
    logger.info(f"Service started on port {cfg.GRPC_PORT}")
    await server.wait_for_termination()

if __name__ == "__main__":
    asyncio.run(run())
