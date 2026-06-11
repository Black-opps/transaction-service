"""
Transaction Model - Canonical Ledger (IMMUTABLE)
"""

import uuid
from datetime import datetime

from sqlalchemy import JSON, Column, DateTime, Index, Numeric, String, UniqueConstraint
from sqlalchemy.dialects.postgresql import UUID
from src.database.base import Base


class Transaction(Base):
    """Canonical Transaction Model - IMMUTABLE LEDGER"""

    __tablename__ = "transactions"

    # Primary identifier
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)

    # Business identifiers
    transaction_id = Column(String, unique=True, index=True, nullable=False)
    hash_key = Column(String, index=True, nullable=False)
    tenant_id = Column(String, index=True, nullable=False)

    # AUDIT TRAIL FIELDS
    upload_file_id = Column(String, index=True, nullable=True)
    uploaded_by = Column(String, nullable=True)
    uploaded_at = Column(DateTime, default=datetime.utcnow)
    parser_version = Column(String, default="1.0.0")

    # Transaction data
    date = Column(DateTime, nullable=False)
    amount = Column(Numeric(18, 2), nullable=False)
    transaction_type = Column(String, nullable=False)
    counterparty = Column(String, nullable=False)
    description = Column(String, default="")
    phone_number = Column(String, default="")
    reference = Column(String, default="")
    balance = Column(Numeric(18, 2), nullable=True)

    # Analytics fields
    category = Column(String, nullable=True, index=True)
    merchant = Column(String, nullable=True, index=True)
    source = Column(String, nullable=False, default="mpesa")
    tags = Column(JSON, nullable=True, default=list)

    # Metadata
    created_at = Column(DateTime, default=datetime.utcnow)

    # Indexes
    __table_args__ = (
        UniqueConstraint("tenant_id", "hash_key", name="uq_tenant_hash"),
        Index("idx_tenant_date", "tenant_id", "date"),
        Index("idx_tenant_type", "tenant_id", "transaction_type"),
        Index("idx_tenant_category", "tenant_id", "category"),
        Index("idx_tenant_merchant", "tenant_id", "merchant"),
        Index("idx_hash_key_tenant", "hash_key", "tenant_id"),
        Index("idx_upload_file_id", "upload_file_id"),
    )

    def to_dict(self):
        """Convert to dictionary for API responses"""
        return {
            "id": self.transaction_id,
            "date": self.date.isoformat(),
            "amount": float(self.amount),
            "type": self.transaction_type,
            "counterparty": self.counterparty,
            "description": self.description,
            "reference": self.reference,
            "balance": float(self.balance) if self.balance else None,
            "category": self.category,
            "merchant": self.merchant,
            "source": self.source,
            "tags": self.tags,
            "uploaded_at": self.uploaded_at.isoformat() if self.uploaded_at else None,
            "parser_version": self.parser_version,
        }
