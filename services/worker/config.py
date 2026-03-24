import os


class WorkerConfig:
    REDIS_URL: str = os.getenv("REDIS_URL", "redis://localhost:6379")
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    WORKER_CONSUMER_GROUP: str = os.getenv("WORKER_CONSUMER_GROUP", "workers")
    WORKER_CONCURRENCY: int = int(os.getenv("WORKER_CONCURRENCY", "4"))
    MAX_STREAM_LENGTH: int = int(os.getenv("MAX_STREAM_LENGTH", "10000"))
    CONSUMER_BLOCK_MS: int = int(os.getenv("CONSUMER_BLOCK_MS", "5000"))
