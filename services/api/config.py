import os


class GatewayConfig:
    INGESTION_GRPC_HOST: str = os.getenv("INGESTION_GRPC_HOST", "localhost")
    INGESTION_GRPC_PORT: int = int(os.getenv("INGESTION_GRPC_PORT", "50051"))
    GATEWAY_PORT: int = int(os.getenv("GATEWAY_PORT", "8080"))
    LOG_LEVEL: str = os.getenv("LOG_LEVEL", "INFO")
    RATE_LIMIT_MAX: int = int(os.getenv("RATE_LIMIT_MAX", "5"))
    RATE_LIMIT_WINDOW: int = int(os.getenv("RATE_LIMIT_WINDOW", "60"))
