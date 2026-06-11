# services/transaction-service/src/repositories/transaction_repository.py
from datetime import datetime
from decimal import Decimal
from typing import List, Optional, Tuple

from sqlalchemy import desc, func
from sqlalchemy.orm import Session

from ..models.transaction import Transaction


class TransactionRepository:
    """
    Repository pattern for Transaction data access.
    EVERY query automatically filters by tenant_id for isolation.
    """

    def __init__(self, db: Session, tenant_id: str):
        self.db = db
        self.tenant_id = tenant_id

    def _apply_tenant_filter(self, query):
        """Apply tenant isolation to any query"""
        return query.filter(Transaction.tenant_id == self.tenant_id)

    def create(self, transaction: Transaction) -> Transaction:
        """Create a single transaction"""
        self.db.add(transaction)
        return transaction

    def create_batch(self, transactions: List[Transaction]) -> int:
        """Create multiple transactions"""
        self.db.add_all(transactions)
        return len(transactions)

    def exists_by_hash_key(self, hash_key: str) -> bool:
        """Check if transaction exists (for deduplication)"""
        query = self.db.query(Transaction).filter(Transaction.hash_key == hash_key)
        query = self._apply_tenant_filter(query)
        return query.first() is not None

    def get_existing_hash_keys(self, hash_keys: List[str]) -> set:
        """Get set of existing hash_keys (batch deduplication)"""
        query = self.db.query(Transaction.hash_key).filter(
            Transaction.hash_key.in_(hash_keys)
        )
        query = self._apply_tenant_filter(query)
        existing = query.all()
        return {row[0] for row in existing}

    def get_transactions(
        self,
        limit: int = 100,
        offset: int = 0,
        transaction_type: Optional[str] = None,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
    ) -> Tuple[List[Transaction], int]:
        """Get transactions with filters - TENANT ISOLATED"""
        query = self.db.query(Transaction)
        query = self._apply_tenant_filter(query)

        if transaction_type:
            query = query.filter(Transaction.transaction_type == transaction_type)

        if start_date:
            query = query.filter(Transaction.date >= start_date)

        if end_date:
            query = query.filter(Transaction.date <= end_date)

        total = query.count()
        transactions = (
            query.order_by(desc(Transaction.date)).offset(offset).limit(limit).all()
        )

        return transactions, total

    def get_stats(self) -> dict:
        """Get aggregated statistics - TENANT ISOLATED"""
        query = self.db.query(
            func.sum(Transaction.amount)
            .filter(Transaction.transaction_type == "received")
            .label("total_in"),
            func.sum(Transaction.amount)
            .filter(Transaction.transaction_type == "sent")
            .label("total_out"),
            func.count(Transaction.id).label("total_count"),
        )
        query = self._apply_tenant_filter(query)

        stats = query.first()

        total_in = Decimal(stats[0] or 0) if stats else Decimal(0)
        total_out = Decimal(stats[1] or 0) if stats else Decimal(0)
        net_flow = total_in - total_out

        return {
            "total_money_in": float(total_in),
            "total_money_out": float(total_out),
            "net_flow": float(net_flow),
            "total_transactions": stats[2] if stats else 0,
        }

    def get_reconciliation(self) -> dict:
        """Get reconciliation stats - TENANT ISOLATED"""
        query = self.db.query(Transaction)
        query = self._apply_tenant_filter(query)

        total_transactions = query.count()

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

        # Check for orphans (transactions without file_id)
        orphans = (
            self.db.query(Transaction)
            .filter(
                Transaction.tenant_id == self.tenant_id,
                Transaction.upload_file_id.is_(None),
            )
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

        return {
            "total_transactions": total_transactions,
            "money_in": float(total_in),
            "money_out": float(total_out),
            "net_flow": float(total_in - total_out),
            "orphan_transactions": orphans,
            "duplicate_hash_keys": duplicates,
            "is_consistent": orphans == 0 and duplicates == 0,
        }
