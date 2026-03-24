import json
import logging
import sys
from datetime import datetime, timezone


class StructuredFormatter(logging.Formatter):
    """JSON structured log formatter for observability pipelines."""

    _RESERVED = frozenset(
        logging.LogRecord("", 0, "", 0, "", (), None).__dict__.keys()
    )

    def format(self, record: logging.LogRecord) -> str:
        entry: dict = {
            "ts": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "msg": record.getMessage(),
        }
        for key, val in record.__dict__.items():
            if key in self._RESERVED or key == "message":
                continue
            try:
                json.dumps(val)
                entry[key] = val
            except (TypeError, ValueError):
                entry[key] = str(val)
        return json.dumps(entry, default=str)


def setup_logging(level: str | None = None) -> None:
    from common.config import Config

    log_level = level or Config.LOG_LEVEL
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(StructuredFormatter())

    root = logging.getLogger()
    root.setLevel(getattr(logging, log_level.upper(), logging.INFO))
    root.handlers = [handler]


def get_logger(name: str) -> logging.Logger:
    return logging.getLogger(name)
