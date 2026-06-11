"""
Global exception handlers for consistent error responses
"""

import logging
import traceback

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from jwt import PyJWTError
from sqlalchemy.exc import IntegrityError, OperationalError

logger = logging.getLogger(__name__)


def setup_exception_handlers(app: FastAPI):
    """Register global exception handlers"""

    @app.exception_handler(HTTPException)
    async def http_exception_handler(request: Request, exc: HTTPException):
        logger.warning(f"HTTP {exc.status_code}: {exc.detail}")
        return JSONResponse(
            status_code=exc.status_code,
            content={
                "error": exc.detail,
                "status_code": exc.status_code,
                "path": request.url.path,
            },
        )

    @app.exception_handler(IntegrityError)
    async def integrity_error_handler(request: Request, exc: IntegrityError):
        logger.error(f"Database integrity error: {exc}")
        return JSONResponse(
            status_code=409,
            content={
                "error": "Database constraint violation",
                "detail": "Duplicate transaction or invalid data",
                "path": request.url.path,
            },
        )

    @app.exception_handler(OperationalError)
    async def operational_error_handler(request: Request, exc: OperationalError):
        logger.error(f"Database operational error: {exc}")
        return JSONResponse(
            status_code=503,
            content={
                "error": "Database connection error",
                "detail": "Service temporarily unavailable",
                "path": request.url.path,
            },
        )

    @app.exception_handler(PyJWTError)
    async def jwt_error_handler(request: Request, exc: PyJWTError):
        logger.warning(f"JWT error: {exc}")
        return JSONResponse(
            status_code=401,
            content={
                "error": "Invalid authentication token",
                "detail": str(exc),
                "path": request.url.path,
            },
        )

    @app.exception_handler(Exception)
    async def general_exception_handler(request: Request, exc: Exception):
        logger.error(f"Unhandled exception: {traceback.format_exc()}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "Internal server error",
                "detail": "An unexpected error occurred",
                "path": request.url.path,
            },
        )
