"""
Business logic for transaction management
"""

import logging
import uuid
from datetime import datetime
from decimal import Decimal
from typing import Any, Dict, List, Optional, Union

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from ..models.transaction import Transaction
from ..schemas.transaction import StatsResponse, TransactionCreate

logger = logging.getLogger(__name__)


class TransactionService:
    """Service layer for transaction operations"""

    def __init__(self, db: Session, tenant_id: str):
        """Initialize with database session and tenant isolation"""
        self.db = db
        self.tenant_id = tenant_id

    def create_transaction(self, transaction_data: TransactionCreate) -> Transaction:
        """Create a single transaction - uses Decimal for money precision with audit trail"""
        db_transaction = Transaction(
            transaction_id=transaction_data.transaction_id,
            hash_key=transaction_data.hash_key,
            tenant_id=self.tenant_id,
            upload_file_id=transaction_data.upload_file_id,
            uploaded_by=transaction_data.uploaded_by,
            parser_version=transaction_data.parser_version or "1.0.0",
            date=datetime.fromisoformat(transaction_data.date),
            amount=Decimal(str(transaction_data.amount)),
            transaction_type=transaction_data.transaction_type,
            counterparty=transaction_data.counterparty,
            description=transaction_data.description or "",
            phone_number=transaction_data.phone_number or "",
            reference=transaction_data.reference or "",
            balance=(
                Decimal(str(transaction_data.balance))
                if transaction_data.balance
                else None
            ),
            category=transaction_data.category or "unknown",
            merchant=transaction_data.merchant,
            source=transaction_data.source or "mpesa",
        )
        self.db.add(db_transaction)
        self.db.commit()
        self.db.refresh(db_transaction)
        return db_transaction

    def create_transactions_batch(
        self, transactions: List[Union[TransactionCreate, Dict[str, Any]]]
    ) -> Dict:
        """
        Create multiple transactions, skipping duplicates and handling rollbacks.

        Now accepts both TransactionCreate objects AND dictionaries.
        This allows the deduplication function to return dicts while maintaining
        compatibility with the batch endpoint.
        """
        saved = 0
        duplicates = 0
        errors = 0

        # Process each transaction individually to avoid batch failures
        for tx_data in transactions:
            try:
                # ✅ FIX: Convert dict to TransactionCreate if needed
                if isinstance(tx_data, dict):
                    # Convert dict to TransactionCreate
                    tx_create = TransactionCreate(
                        transaction_id=tx_data.get("transaction_id"),
                        hash_key=tx_data.get("hash_key"),
                        upload_file_id=tx_data.get("upload_file_id"),
                        uploaded_by=tx_data.get("uploaded_by", self.tenant_id),
                        parser_version=tx_data.get("parser_version", "1.0.0"),
                        date=tx_data.get("date"),
                        amount=tx_data.get("amount"),
                        transaction_type=tx_data.get("transaction_type"),
                        counterparty=tx_data.get("counterparty"),
                        description=tx_data.get("description", ""),
                        phone_number=tx_data.get("phone_number", ""),
                        reference=tx_data.get("reference", ""),
                        balance=tx_data.get("balance"),
                        category=tx_data.get("category", "unknown"),
                        merchant=tx_data.get("merchant"),
                        source=tx_data.get("source", "mpesa"),
                    )
                else:
                    tx_create = tx_data

                # Check if transaction already exists
                existing = (
                    self.db.query(Transaction)
                    .filter(Transaction.transaction_id == tx_create.transaction_id)
                    .first()
                )

                if existing:
                    duplicates += 1
                    continue

                # Create new transaction
                transaction = Transaction(
                    id=str(uuid.uuid4()),
                    transaction_id=tx_create.transaction_id,
                    hash_key=tx_create.hash_key,
                    tenant_id=self.tenant_id,
                    date=datetime.fromisoformat(tx_create.date),
                    amount=Decimal(str(tx_create.amount)),
                    transaction_type=tx_create.transaction_type,
                    counterparty=tx_create.counterparty,
                    description=tx_create.description or "",
                    phone_number=tx_create.phone_number or "",
                    reference=tx_create.reference or "",
                    balance=(
                        Decimal(str(tx_create.balance)) if tx_create.balance else None
                    ),
                    category=tx_create.category or "unknown",
                    source=tx_create.source or "mpesa",
                    created_at=datetime.utcnow(),
                )
                self.db.add(transaction)
                saved += 1

                # Commit every 50 transactions to avoid memory issues
                if saved % 50 == 0:
                    self.db.commit()

            except Exception as e:
                errors += 1
                tx_id = (
                    tx_data.get("transaction_id")
                    if isinstance(tx_data, dict)
                    else tx_data.transaction_id
                )
                logger.error(f"Error inserting {tx_id}: {e}")
                # Rollback the failed transaction but continue with next
                self.db.rollback()

        # Final commit for remaining transactions
        if saved % 50 != 0:
            try:
                self.db.commit()
            except Exception as e:
                logger.error(f"Final commit failed: {e}")
                self.db.rollback()

        logger.info(
            f"Batch insert: saved={saved}, duplicates={duplicates}, errors={errors}, total={len(transactions)}"
        )
        return {
            "saved": saved,
            "duplicates": duplicates,
            "errors": errors,
            "total": len(transactions),
        }

    def get_transactions(
        self,
        limit: int = 100,
        offset: int = 0,
        transaction_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        category: Optional[str] = None,
        merchant: Optional[str] = None,
    ) -> List[Transaction]:
        """Get transactions with filters - MUST enforce tenant isolation"""
        query = self.db.query(Transaction).filter(
            Transaction.tenant_id == self.tenant_id
        )

        logger.info(f"Querying transactions for tenant: {self.tenant_id}")

        if transaction_type:
            query = query.filter(Transaction.transaction_type == transaction_type)

        if start_date:
            query = query.filter(Transaction.date >= datetime.fromisoformat(start_date))

        if end_date:
            query = query.filter(Transaction.date <= datetime.fromisoformat(end_date))

        if category:
            query = query.filter(Transaction.category == category)

        if merchant:
            query = query.filter(Transaction.merchant == merchant)

        transactions = (
            query.order_by(desc(Transaction.date)).offset(offset).limit(limit).all()
        )

        # SECURITY: Double-check all returned transactions belong to this tenant
        for tx in transactions:
            if tx.tenant_id != self.tenant_id:
                logger.error(
                    f"SECURITY VIOLATION: Transaction {tx.id} belongs to tenant {tx.tenant_id} but requested by {self.tenant_id}"
                )
                raise PermissionError(f"Tenant isolation violation! Access denied.")

        return transactions

    # ============================================================
    # ✅ NEW: TOTAL COUNT METHOD (for correct pagination)
    # ============================================================

    def get_transaction_count(
        self,
        transaction_type: Optional[str] = None,
        start_date: Optional[str] = None,
        end_date: Optional[str] = None,
        category: Optional[str] = None,
        merchant: Optional[str] = None,
    ) -> int:
        """
        Return total count of transactions matching filters (BEFORE pagination).

        This is used by the API to return the real total, not just the page size.
        """
        query = self.db.query(func.count(Transaction.id)).filter(
            Transaction.tenant_id == self.tenant_id
        )

        if transaction_type:
            query = query.filter(Transaction.transaction_type == transaction_type)

        if start_date:
            query = query.filter(Transaction.date >= datetime.fromisoformat(start_date))

        if end_date:
            query = query.filter(Transaction.date <= datetime.fromisoformat(end_date))

        if category:
            query = query.filter(Transaction.category == category)

        if merchant:
            query = query.filter(Transaction.merchant == merchant)

        result = query.scalar()
        return int(result) if result is not None else 0

    def get_stats(self) -> StatsResponse:
        """Get transaction statistics - tenant isolated"""
        total_in_result = (
            self.db.query(func.sum(Transaction.amount))
            .filter(
                Transaction.tenant_id == self.tenant_id,
                Transaction.transaction_type == "received",
            )
            .scalar()
        )

        total_out_result = (
            self.db.query(func.sum(Transaction.amount))
            .filter(
                Transaction.tenant_id == self.tenant_id,
                Transaction.transaction_type == "sent",
            )
            .scalar()
        )

        total_in = total_in_result if total_in_result is not None else Decimal(0)
        total_out = total_out_result if total_out_result is not None else Decimal(0)

        total_count = (
            self.db.query(Transaction)
            .filter(Transaction.tenant_id == self.tenant_id)
            .count()
        )

        # Category breakdown for analytics
        category_breakdown = {}
        categories = (
            self.db.query(
                Transaction.category,
                func.sum(Transaction.amount).label("total"),
                func.count(Transaction.id).label("count"),
            )
            .filter(
                Transaction.tenant_id == self.tenant_id,
                Transaction.category.isnot(None),
            )
            .group_by(Transaction.category)
            .all()
        )

        for category, total, count in categories:
            category_breakdown[category] = {
                "total": float(total),
                "count": count,
                "average": float(total / count) if count > 0 else 0,
            }

        logger.info(
            f"Stats for tenant {self.tenant_id}: in={total_in}, out={total_out}, count={total_count}"
        )

        return StatsResponse(
            tenant_id=self.tenant_id,
            total_money_in=float(total_in),
            total_money_out=float(total_out),
            net_flow=float(total_in - total_out),
            total_transactions=total_count,
            category_breakdown=category_breakdown if category_breakdown else None,
        )

    def get_reconciliation(self) -> dict:
        """Get reconciliation data for tenant isolation"""
        total_in = (
            self.db.query(func.sum(Transaction.amount))
            .filter(
                Transaction.tenant_id == self.tenant_id,
                Transaction.transaction_type == "received",
            )
            .scalar()
            or 0
        )

        total_out = (
            self.db.query(func.sum(Transaction.amount))
            .filter(
                Transaction.tenant_id == self.tenant_id,
                Transaction.transaction_type == "sent",
            )
            .scalar()
            or 0
        )

        total_transactions = (
            self.db.query(Transaction)
            .filter(Transaction.tenant_id == self.tenant_id)
            .count()
        )

        # Check for duplicates
        duplicates = (
            self.db.query(Transaction.hash_key)
            .filter(Transaction.tenant_id == self.tenant_id)
            .group_by(Transaction.hash_key)
            .having(func.count() > 1)
            .count()
        )

        # Check for transactions without source (orphans)
        orphans = (
            self.db.query(Transaction)
            .filter(
                Transaction.tenant_id == self.tenant_id,
                Transaction.upload_file_id.is_(None),
            )
            .count()
        )

        return {
            "money_in": float(total_in) if total_in else 0,
            "money_out": float(total_out) if total_out else 0,
            "net_flow": float(total_in - total_out),
            "total_transactions": total_transactions,
            "orphan_transactions": orphans,
            "duplicate_hash_keys": duplicates,
            "is_consistent": duplicates == 0 and orphans == 0,
        }
