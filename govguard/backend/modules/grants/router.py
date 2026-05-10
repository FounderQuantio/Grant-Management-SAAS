"""GovGuard™ — Grants Module"""
import uuid
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user, require_role, UserContext
from core.db import get_db, set_tenant
from core.models import Grant
from core.exceptions import GrantNotFound, GrantAlreadyActive, ConflictError


class GrantCreate(BaseModel):
    award_number: str
    agency: str
    program_cfda: Optional[str] = None
    period_start: str
    period_end: str
    total_amount: float
    budget_json: dict = {}


class GrantResponse(BaseModel):
    id: UUID
    award_number: str
    agency: str
    status: str
    total_amount: float
    compliance_score: Optional[float]
    created_at: datetime
    model_config = {"from_attributes": True}


router = APIRouter()


@router.post("", response_model=GrantResponse, status_code=201)
async def create_grant(
    data: GrantCreate,
    user: UserContext = Depends(require_role("compliance_officer")),
    db: AsyncSession = Depends(get_db),
):
    await set_tenant(db, str(user.tenant_id))
    # Check for duplicate award number in tenant
    existing = await db.execute(
        select(Grant).where(and_(Grant.tenant_id == user.tenant_id, Grant.award_number == data.award_number))
    )
    if existing.scalar_one_or_none():
        raise ConflictError(f"Grant {data.award_number} already exists")

    grant = Grant(
        id=uuid.uuid4(),
        tenant_id=user.tenant_id,
        award_number=data.award_number,
        agency=data.agency,
        program_cfda=data.program_cfda,
        period_start=data.period_start,
        period_end=data.period_end,
        total_amount=data.total_amount,
        budget_json=data.budget_json,
        status="draft",
        created_by=user.id,
    )
    db.add(grant)
    await db.commit()
    await db.refresh(grant)
    return GrantResponse.model_validate(grant)


@router.get("", response_model=dict)
async def list_grants(
    status: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await set_tenant(db, str(user.tenant_id))
    q = select(Grant).where(Grant.tenant_id == user.tenant_id)
    if status:
        q = q.where(Grant.status == status)
    result = await db.execute(q.offset((page - 1) * limit).limit(limit))
    grants = result.scalars().all()
    return {
        "grants": [GrantResponse.model_validate(g).model_dump() for g in grants],
        "total": len(grants),
        "page": page,
        "limit": limit,
    }


@router.get("/{grant_id}", response_model=GrantResponse)
async def get_grant(
    grant_id: UUID,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await set_tenant(db, str(user.tenant_id))
    result = await db.execute(
        select(Grant).where(and_(Grant.id == grant_id, Grant.tenant_id == user.tenant_id))
    )
    grant = result.scalar_one_or_none()
    if not grant:
        raise GrantNotFound()
    return GrantResponse.model_validate(grant)


@router.post("/{grant_id}/activate")
async def activate_grant(
    grant_id: UUID,
    user: UserContext = Depends(require_role("compliance_officer")),
    db: AsyncSession = Depends(get_db),
):
    await set_tenant(db, str(user.tenant_id))
    result = await db.execute(
        select(Grant).where(and_(Grant.id == grant_id, Grant.tenant_id == user.tenant_id))
    )
    grant = result.scalar_one_or_none()
    if not grant:
        raise GrantNotFound()
    if grant.status == "active":
        raise GrantAlreadyActive()

    grant.status = "active"
    grant.activated_at = datetime.now(timezone.utc)
    await db.commit()

    # Seed compliance controls
    try:
        from modules.compliance_engine.service import ComplianceService
        svc = ComplianceService(db)
        await svc.seed_controls_for_grant(grant_id, user.tenant_id)
    except Exception:
        pass

    return {"status": "active", "activated_at": grant.activated_at.isoformat()}
