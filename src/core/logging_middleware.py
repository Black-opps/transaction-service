"""
Request/response logging middleware
"""

import logging
import time

from fastapi import Request
from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger(__name__)


class LoggingMiddleware(BaseHTTPMiddleware):
    """Log all requests and their duration"""

    async def dispatch(self, request: Request, call_next):
        start_time = time.time()

        # Log request
        logger.info(f"→ {request.method} {request.url.path}")

        # Process request
        response = await call_next(request)

        # Calculate duration
        duration = (time.time() - start_time) * 1000

        # Log response
        logger.info(
            f"← {response.status_code} {request.method} {request.url.path} ({duration:.2f}ms)"
        )

        # Add duration header
        response.headers["X-Response-Time"] = f"{duration:.2f}ms"

        return response
