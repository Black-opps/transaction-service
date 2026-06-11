"""
API Routes for Transaction Service
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, text  # ADD text here
from sqlalchemy.orm import Session

from ..core.dependencies import get_current_tenant
from ..database.session import get_db
from ..models.transaction import Transaction
from ..schemas.transaction import BatchResponse, BatchTransactionCreate, StatsResponse
from ..services.transaction_service import TransactionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/transactions", tags=["transactions"])


@router.post("/batch", response_model=BatchResponse)
async def create_transactions_batch(
    batch: BatchTransactionCreate,
    current_tenant: dict = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Create multiple transactions (batch insert)"""
    tenant_id = current_tenant["tenant_id"]
    service = TransactionService(db, tenant_id)
    return service.create_transactions_batch(batch.transactions)


@router.get("/", response_model=dict)
async def get_transactions(
    current_tenant: dict = Depends(get_current_tenant),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    transaction_type: Optional[str] = Query(None),
    start_date: Optional[str] = Query(None),
    end_date: Optional[str] = Query(None),
    category: Optional[str] = Query(None),
    merchant: Optional[str] = Query(None),
    db: Session = Depends(get_db),
):
    """Get all transactions for a tenant - TENANT ISOLATED"""
    tenant_id = current_tenant["tenant_id"]
    logger.info(f"Authenticated tenant: {tenant_id} accessing transactions")

    service = TransactionService(db, tenant_id)
    transactions = service.get_transactions(
        limit=limit,
        offset=offset,
        transaction_type=transaction_type,
        start_date=start_date,
        end_date=end_date,
        category=category,
        merchant=merchant,
    )

    return {
        "tenant_id": tenant_id,
        "total": len(transactions),
        "limit": limit,
        "offset": offset,
        "transactions": [tx.to_dict() for tx in transactions],
    }


@router.get("/stats", response_model=StatsResponse)
async def get_stats(
    current_tenant: dict = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Get transaction statistics for a tenant"""
    tenant_id = current_tenant["tenant_id"]
    service = TransactionService(db, tenant_id)
    return service.get_stats()


@router.get("/reconcile")
async def reconcile_ledger(
    current_tenant: dict = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Verify ledger integrity"""
    tenant_id = current_tenant["tenant_id"]
    service = TransactionService(db, tenant_id)
    reconciliation = service.get_reconciliation()

    return {
        "tenant_id": tenant_id,
        "reconciled_at": datetime.utcnow().isoformat(),
        "totals": {
            "money_in": reconciliation["money_in"],
            "money_out": reconciliation["money_out"],
            "net_flow": reconciliation["net_flow"],
            "transaction_count": reconciliation["total_transactions"],
        },
        "integrity": {
            "orphan_transactions": reconciliation["orphan_transactions"],
            "duplicate_hash_keys": reconciliation["duplicate_hash_keys"],
            "is_consistent": reconciliation["is_consistent"],
        },
        "status": "verified" if reconciliation["is_consistent"] else "inconsistent",
    }


@router.get("/health")
async def health_check(db: Session = Depends(get_db)):
    """Health check endpoint"""
    try:
        # FIXED: Use text() for SQLAlchemy 2.x
        db.execute(text("SELECT 1"))
        return {
            "status": "healthy",
            "service": "transaction-service",
            "database": "connected",
        }
    except Exception as e:
        logger.error(f"Health check failed: {e}")
        return {
            "status": "unhealthy",
            "service": "transaction-service",
            "database": "disconnected",
            "error": str(e),
        }
