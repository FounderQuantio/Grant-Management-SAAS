"""GovGuard™ — Compliance Schemas"""
from datetime import datetime
from decimal import Decimal
from typing import Optional
from uuid import UUID
from pydantic import BaseModel


class ControlResponse(BaseModel):
    id: UUID
    grant_id: UUID
    control_code: str
    cfr_clause: Optional[str]
    gao_principle: Optional[str]
    domain: str
    status: str
    last_tested: Optional[datetime]
    evidence_s3_key: Optional[str]
    remediation_note: Optional[str]
    model_config = {"from_attributes": True}


class ControlListResponse(BaseModel):
    controls: list[ControlResponse]
    score: Decimal
    total: int
    passing: int
    failing: int


class ControlUpdate(BaseModel):
    status: str
    evidence_note: Optional[str] = None


class ComplianceRunRequest(BaseModel):
    grant_id: UUID
    control_codes: Optional[list[str]] = None


class ComplianceRunResponse(BaseModel):
    job_id: UUID
    controls_queued: int


class SoDResponse(BaseModel):
    violations: list[dict]
    matrix_snapshot: dict
