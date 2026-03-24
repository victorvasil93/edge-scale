import os


class IngestionConfig:
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    GRPC_PORT: int = int(os.getenv("GRPC_PORT", "50051"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    RESULT_TIMEOUT: float = float(os.getenv("RESULT_TIMEOUT", "30.0"))
    FILE_RESULT_TIMEOUT: float = float(os.getenv("FILE_RESULT_TIMEOUT", "60.0"))
    MAX_STREAM_LENGTH: int = int(os.getenv("MAX_STREAM_LENGTH", "10000"))
    CONSUMER_BLOCK_MS: int = int(os.getenv("CONSUMER_BLOCK_MS", "5000"))
