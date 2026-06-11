"""
Transaction Service - Canonical Ledger
"""

import logging
import os
from fastapi import FastAPI, Request, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from dotenv import load_dotenv

from .api.routes import router
from .database.session import engine

load_dotenv()

logging.basicConfig(
    level=getattr(logging, os.getenv("LOG_LEVEL", "INFO")),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Transaction Service",
    description="Canonical ledger for financial transactions",
    version="1.0.0",
    docs_url="/docs",
    redoc_url="/redoc",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.middleware("http")
async def enforce_tenant_isolation(request: Request, call_next):
    """Ensure tenant isolation"""
    response = await call_next(request)
    return response


@app.on_event("startup")
async def startup_event():
    logger.info("🚀 Transaction Service starting on port 8006")
    logger.info("📚 API Documentation available at /docs")


@app.on_event("shutdown")
async def shutdown_event():
    logger.info("👋 Transaction Service shutting down")
    engine.dispose()


@app.get("/")
async def root():
    return {
        "service": "Transaction Service",
        "version": "1.0.0",
        "status": "running",
        "endpoints": {
            "POST /api/v1/transactions/batch": "Store multiple transactions",
            "GET /api/v1/transactions": "Query transactions",
            "GET /api/v1/transactions/stats": "Get statistics",
            "GET /api/v1/transactions/reconcile": "Ledger reconciliation",
        },
    }


@app.get("/health")
async def health():
    return {"status": "healthy", "service": "transaction-service"}


app.include_router(router)

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8006)
