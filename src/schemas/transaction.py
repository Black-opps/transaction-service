"""
Pydantic schemas for request/response validation
"""

from datetime import datetime
from decimal import Decimal
from typing import List, Optional

from pydantic import BaseModel, Field, validator


class TransactionCreate(BaseModel):
    """Schema for creating a transaction with audit trail"""

    transaction_id: str
    hash_key: str
    date: str
    amount: Decimal  # Changed from float to Decimal
    transaction_type: str
    counterparty: str
    description: Optional[str] = ""
    phone_number: Optional[str] = ""
    reference: Optional[str] = ""
    balance: Optional[Decimal] = None  # Changed from float to Decimal

    # New fields
    category: Optional[str] = None
    merchant: Optional[str] = None
    source: Optional[str] = "mpesa"

    # Audit trail fields
    upload_file_id: Optional[str] = None
    uploaded_by: Optional[str] = None
    parser_version: Optional[str] = "1.0.0"

    @validator("amount")
    def amount_positive(cls, v):
        if v <= 0:
            raise ValueError("Amount must be positive")
        return v

    @validator("transaction_type")
    def validate_type(cls, v):
        allowed_types = [
            "sent",
            "received",
            "withdrawal",
            "deposit",
            "airtime",
            "paybill",
            "till",
            "charge",
            "reversal",
            "loan",
            "interest",
        ]
        if v not in allowed_types:
            raise ValueError(f"Transaction type must be one of: {allowed_types}")
        return v


class BatchTransactionCreate(BaseModel):
    """Schema for batch creation"""

    transactions: List[TransactionCreate]
    tenant_id: str


class TransactionResponse(BaseModel):
    """Schema for transaction response"""

    id: str
    date: str
    amount: float  # Convert Decimal to float for JSON response
    type: str
    counterparty: str
    description: str
    reference: str
    balance: Optional[float] = None
    category: Optional[str] = None
    merchant: Optional[str] = None
    source: str


class StatsResponse(BaseModel):
    """Schema for statistics response"""

    tenant_id: str
    total_money_in: float
    total_money_out: float
    net_flow: float
    total_transactions: int
    category_breakdown: Optional[dict] = None


class BatchResponse(BaseModel):
    """Schema for batch creation response"""

    saved: int
    duplicates: int
    total: int
