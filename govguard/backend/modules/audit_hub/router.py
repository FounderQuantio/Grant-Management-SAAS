"""GovGuard™ — Audit Hub Module"""
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
from core.models import AuditFinding, CorrectiveActionPlan
from core.exceptions import NotFoundError


class CAPCreate(BaseModel):
    finding_id: UUID
    response_text: str
    due_date: str
    assignee_id: Optional[UUID] = None


class CAPUpdate(BaseModel):
    status: str
    resolution_note: Optional[str] = None


router = APIRouter()


@router.get("/findings")
async def list_findings(
    grant_id: Optional[UUID] = Query(None),
    status: Optional[str] = Query(None),
    user: UserContext = Depends(require_role("compliance_officer")),
    db: AsyncSession = Depends(get_db),
):
    await set_tenant(db, str(user.tenant_id))
    q = select(AuditFinding).where(AuditFinding.tenant_id == user.tenant_id)
    if grant_id:
        q = q.where(AuditFinding.grant_id == grant_id)
    if status:
        q = q.where(AuditFinding.status == status)
    result = await db.execute(q)
    findings = result.scalars().all()
    open_count = sum(1 for f in findings if f.status == "open")
    return {"findings": [{"id": str(f.id), "finding_ref": f.finding_ref, "category": f.category,
                          "severity": f.severity, "status": f.status, "due_date": str(f.due_date) if f.due_date else None}
                         for f in findings], "open_count": open_count, "overdue_count": 0}


@router.post("/cap", status_code=201)
async def create_cap(
    data: CAPCreate,
    user: UserContext = Depends(require_role("compliance_officer")),
    db: AsyncSession = Depends(get_db),
):
    await set_tenant(db, str(user.tenant_id))
    cap = CorrectiveActionPlan(
        id=uuid.uuid4(),
        tenant_id=user.tenant_id,
        finding_id=data.finding_id,
        response_text=data.response_text,
        due_date=data.due_date,
        assignee_id=data.assignee_id,
        status="open",
    )
    db.add(cap)
    await db.commit()
    return {"cap_id": str(cap.id), "status": "open", "due_date": str(cap.due_date)}


@router.patch("/cap/{cap_id}")
async def update_cap(
    cap_id: UUID,
    data: CAPUpdate,
    user: UserContext = Depends(require_role("compliance_officer")),
    db: AsyncSession = Depends(get_db),
):
    await set_tenant(db, str(user.tenant_id))
    result = await db.execute(
        select(CorrectiveActionPlan).where(
            and_(CorrectiveActionPlan.id == cap_id, CorrectiveActionPlan.tenant_id == user.tenant_id)
        )
    )
    cap = result.scalar_one_or_none()
    if not cap:
        raise NotFoundError("CAP not found")
    cap.status = data.status
    if data.resolution_note:
        cap.resolution_note = data.resolution_note
    if data.status == "closed":
        cap.closed_at = datetime.now(timezone.utc)
    await db.commit()
    return {"id": str(cap.id), "status": cap.status, "closed_at": cap.closed_at.isoformat() if cap.closed_at else None}


@router.post("/evidence-package", status_code=202)
async def create_evidence_package(
    body: dict,
    user: UserContext = Depends(require_role("compliance_officer")),
):
    job_id = uuid.uuid4()
    try:
        from workers.audit_tasks import build_evidence_package
        build_evidence_package.delay(
            str(job_id),
            str(body.get("grant_id", "")),
            str(user.tenant_id),
            body.get("finding_ids"),
        )
    except Exception:
        pass
    return {"job_id": str(job_id), "estimated_seconds": 30}


@router.get("/evidence-package/{job_id}")
async def get_evidence_package(
    job_id: UUID,
    user: UserContext = Depends(get_current_user),
):
    from core.cache import cache_get
    result = await cache_get(f"ep:{job_id}")
    if not result:
        return {"status": "processing"}
    return result
