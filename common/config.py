import os


class Config:
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    GRPC_PORT: int = int(os.getenv("GRPC_PORT", "50051"))
    GATEWAY_PORT: int = int(os.getenv("GATEWAY_PORT", "8080"))
    INGESTION_GRPC_HOST: str = os.getenv("INGESTION_GRPC_HOST", "localhost")
    INGESTION_GRPC_PORT: int = int(os.getenv("INGESTION_GRPC_PORT", "50051"))
    RESULT_TIMEOUT: float = float(os.getenv("RESULT_TIMEOUT", "30.0"))
    FILE_RESULT_TIMEOUT: float = float(os.getenv("FILE_RESULT_TIMEOUT", "60.0"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    WORKER_CONSUMER_GROUP: str = os.getenv("WORKER_CONSUMER_GROUP", "workers")
    WORKER_CONCURRENCY: int = int(os.getenv("WORKER_CONCURRENCY", "4"))
    MAX_STREAM_LENGTH: int = int(os.getenv("MAX_STREAM_LENGTH", "10000"))
    CONSUMER_BLOCK_MS: int = int(os.getenv("CONSUMER_BLOCK_MS", "5000"))
