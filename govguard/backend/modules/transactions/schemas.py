"""GovGuard™ — Transaction Schemas"""
from datetime import date, datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID
from pydantic import BaseModel, Field, field_validator


class TransactionCreate(BaseModel):
    grant_id: UUID
    vendor_id: UUID
    amount: Decimal = Field(gt=0, decimal_places=2)
    invoice_ref: str = Field(min_length=1, max_length=255)
    tx_date: date
    cost_category: str = Field(min_length=1, max_length=100)


class TransactionFlagUpdate(BaseModel):
    flag_status: str = Field(pattern="^(approved|rejected)$")
    justification: str = Field(min_length=10, max_length=2000)


class TransactionResponse(BaseModel):
    id: UUID
    grant_id: UUID
    vendor_id: UUID
    amount: Decimal
    invoice_ref: str
    cost_category: str
    tx_date: date
    risk_score: Optional[Decimal]
    flag_status: str
    flag_reason: Optional[str]
    reviewed_by: Optional[UUID]
    reviewed_at: Optional[datetime]
    created_at: datetime
    queued: bool = False

    model_config = {"from_attributes": True}


class RiskScoreResponse(BaseModel):
    score: Decimal
    feature_weights: dict
    model_version: str
    explanation: str
    threshold: float = 75.0
    is_high_risk: bool


class BulkUploadResponse(BaseModel):
    job_id: UUID
    queued_count: int


class TransactionListResponse(BaseModel):
    transactions: list[TransactionResponse]
    total: int
    page: int
    limit: int
