import logging
import sys
import uuid
from contextvars import ContextVar
from datetime import datetime

# Context variable for request ID propagation
request_id_var: ContextVar[str] = ContextVar("request_id", default="unknown")


class StructuredLogger:
    """Produces JSON logs for observability"""

    @staticmethod
    def log(level: str, message: str, **kwargs):
        log_entry = {
            "timestamp": datetime.utcnow().isoformat(),
            "level": level,
            "message": message,
            "request_id": request_id_var.get(),
            **kwargs,
        }
        print(f"LOG: {log_entry}")  # In production, send to stdout for log aggregation


def get_logger(name: str):
    return logging.getLogger(name)


# Configure root logger
logging.basicConfig(level=logging.INFO)
