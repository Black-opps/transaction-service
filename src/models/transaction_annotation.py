import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text
from sqlalchemy.dialects.postgresql import UUID
from src.database.base import Base


class TransactionAnnotation(Base):
    """
    User-editable annotations for transactions
    This allows users to modify categories/notes without changing the immutable ledger
    """

    __tablename__ = "transaction_annotations"

    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    transaction_id = Column(
        String, ForeignKey("transactions.transaction_id"), nullable=False, index=True
    )
    tenant_id = Column(String, index=True, nullable=False)

    # User-editable fields
    category = Column(String, nullable=True)
    notes = Column(Text, nullable=True)
    tags = Column(String, nullable=True)  # Comma-separated tags

    # Audit trail for annotations
    created_by = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_by = Column(String, nullable=True)
    updated_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("idx_annotation_transaction", "transaction_id"),
        Index("idx_annotation_tenant", "tenant_id"),
    )
