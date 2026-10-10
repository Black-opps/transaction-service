"""
API Routes for Transaction Service
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, text
from sqlalchemy.orm import Session

from ..core.dependencies import get_current_tenant
from ..database.session import get_db
from ..models.transaction import Transaction
from ..schemas.transaction import BatchResponse, BatchTransactionCreate, StatsResponse
from ..services.transaction_service import TransactionService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/transactions", tags=["transactions"])


# ============================================================
# ✅ DEDUPLICATION HELPER - FIXED
# ============================================================


def deduplicate_transactions(
    transactions: List[Any],  # Accepts both dict and Pydantic models
) -> List[Dict[str, Any]]:
    """
    Deduplicate transactions that are identical (same timestamp, counterparty, description).

    This handles Fuliza split transactions where one payment is split
    into multiple entries at the exact same timestamp.
    """
    if not transactions:
        return []

    seen = {}
    deduped = []
    merged_count = 0

    for txn in transactions:
        # ✅ FIX: Handle both dict and Pydantic model
        if hasattr(txn, "model_dump"):
            # Pydantic v2
            txn_dict = txn.model_dump()
        elif hasattr(txn, "dict"):
            # Pydantic v1
            txn_dict = txn.dict()
        elif isinstance(txn, dict):
            # Already a dict
            txn_dict = txn
        else:
            # Fallback: convert to dict using vars if available
            try:
                txn_dict = vars(txn)
            except Exception:
                logger.warning(f"⚠️ Cannot convert transaction to dict: {type(txn)}")
                continue

        # Create a key from unique fields (timestamp + counterparty + description)
        key = (
            txn_dict.get("date", ""),  # ISO format date
            txn_dict.get("counterparty", ""),
            txn_dict.get("description", "")[:50],  # Truncate for matching
            txn_dict.get("transaction_type", ""),
        )

        if key in seen:
            # Merge: Add amounts and combine
            existing = seen[key]
            existing["amount"] += txn_dict.get("amount", 0)
            existing["merged_count"] = existing.get("merged_count", 1) + 1
            merged_count += 1
        else:
            # New transaction
            txn_dict["merged_count"] = 1
            seen[key] = txn_dict
            deduped.append(txn_dict)

    if merged_count > 0:
        logger.info(
            f"✅ Merged {merged_count} duplicate transactions into "
            f"{len(deduped)} unique transactions"
        )

        # Log details of merged transactions for debugging
        for txn in deduped:
            if txn.get("merged_count", 1) > 1:
                logger.debug(
                    f"   Merged {txn['merged_count']} transactions: "
                    f"{txn.get('counterparty', 'Unknown')} - "
                    f"KES {txn.get('amount', 0):,.2f} at {txn.get('date', '')}"
                )

    return deduped


# ============================================================
# API ENDPOINTS
# ============================================================


@router.post("/batch", response_model=BatchResponse)
async def create_transactions_batch(
    batch: BatchTransactionCreate,
    current_tenant: dict = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """Create multiple transactions (batch insert) with deduplication"""
    tenant_id = current_tenant["tenant_id"]

    # ✅ Deduplicate before saving (handles Pydantic models)
    clean_transactions = deduplicate_transactions(batch.transactions)

    if len(clean_transactions) != len(batch.transactions):
        logger.info(
            f"📊 Deduplicated: {len(batch.transactions)} → {len(clean_transactions)} transactions"
        )

    service = TransactionService(db, tenant_id)
    return service.create_transactions_batch(clean_transactions)


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
    """
    Get transactions for a tenant - TENANT ISOLATED.

    Returns the REAL total count (not just the page size) so callers
    can implement correct pagination.
    """
    tenant_id = current_tenant["tenant_id"]
    logger.info(f"Authenticated tenant: {tenant_id} accessing transactions")

    service = TransactionService(db, tenant_id)

    # ✅ FIX: Get total count BEFORE pagination
    total_count = service.get_transaction_count(
        transaction_type=transaction_type,
        start_date=start_date,
        end_date=end_date,
        category=category,
        merchant=merchant,
    )

    transactions = service.get_transactions(
        limit=limit,
        offset=offset,
        transaction_type=transaction_type,
        start_date=start_date,
        end_date=end_date,
        category=category,
        merchant=merchant,
    )

    # Convert to dict with merged_count info if available
    transactions_data = []
    for tx in transactions:
        tx_dict = tx.to_dict()
        # Add merged_count if present (for transparency)
        if hasattr(tx, "merged_count"):
            tx_dict["merged_count"] = tx.merged_count
        transactions_data.append(tx_dict)

    return {
        "tenant_id": tenant_id,
        "total": total_count,  # ✅ FIX: real total, not len(transactions_data)
        "limit": limit,
        "offset": offset,
        "transactions": transactions_data,
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


# ============================================================
# ✅ DEBUG ENDPOINT - Check for duplicates
# ============================================================


@router.get("/debug/duplicates")
async def check_duplicates(
    current_tenant: dict = Depends(get_current_tenant),
    db: Session = Depends(get_db),
):
    """
    DEBUG: Check for duplicate transactions in the database.
    Returns transactions that appear to be duplicates (same date, counterparty, description).
    """
    tenant_id = current_tenant["tenant_id"]

    # SQL query to find duplicates
    query = text("""
        SELECT 
            DATE(date) as txn_date,
            counterparty,
            description,
            COUNT(*) as count,
            SUM(amount) as total_amount,
            array_agg(id) as ids
        FROM transactions
        WHERE tenant_id = :tenant_id
        GROUP BY DATE(date), counterparty, description
        HAVING COUNT(*) > 1
        ORDER BY count DESC
    """)

    result = db.execute(query, {"tenant_id": tenant_id})
    duplicates = result.fetchall()

    return {
        "tenant_id": tenant_id,
        "duplicate_groups": len(duplicates),
        "duplicates": [
            {
                "date": str(r.txn_date),
                "counterparty": r.counterparty,
                "description": r.description[:100],
                "count": r.count,
                "total_amount": float(r.total_amount),
                "ids": r.ids[:10],  # Show first 10 IDs
            }
            for r in duplicates[:20]  # Limit to 20 groups
        ],
        "message": "Run this to find and merge duplicates in the database",
    }
