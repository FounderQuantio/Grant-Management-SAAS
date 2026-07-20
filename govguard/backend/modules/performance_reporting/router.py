"""GovGuard™ — Performance Reporting Module (2 CFR 200.329)"""
from datetime import date, datetime, timezone
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user_or_service as get_current_user, UserContext
from core.db import get_db, set_tenant
from core.models import Grant, PerformanceReport
from core.exceptions import GrantNotFound
from modules.performance_reporting.service import expected_quarterly_periods

router = APIRouter()


class ReportSubmit(BaseModel):
    period_label: str
    narrative: Optional[str] = None


@router.get("/grants/{grant_id}")
async def list_periods(
    grant_id: UUID,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    """List expected reporting periods for a grant, merged with actual submission status."""
    await set_tenant(db, str(user.tenant_id))
    result = await db.execute(
        select(Grant).where(and_(Grant.id == grant_id, Grant.tenant_id == user.tenant_id))
    )
    grant = result.scalar_one_or_none()
    if not grant:
        raise GrantNotFound()

    periods = expected_quarterly_periods(grant.period_start, grant.period_end)

    sub_result = await db.execute(
        select(PerformanceReport).where(PerformanceReport.grant_id == grant_id)
    )
    submissions = {s.period_label: s for s in sub_result.scalars().all()}

    today = date.today()
    rows = []
    for p in periods:
        sub = submissions.get(p["label"])
        overdue = today > p["due_date"] and sub is None
        rows.append({
            "period_label": p["label"],
            "period_end": p["period_end"].isoformat(),
            "due_date": p["due_date"].isoformat(),
            "submitted_at": sub.submitted_at.isoformat() if sub and sub.submitted_at else None,
            "narrative": sub.narrative if sub else None,
            "status": "submitted" if sub else ("overdue" if overdue else "upcoming"),
        })
    return {"grant_id": str(grant_id), "periods": rows}


@router.post("/grants/{grant_id}", status_code=201)
async def submit_report(
    grant_id: UUID,
    data: ReportSubmit,
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

    existing_result = await db.execute(
        select(PerformanceReport).where(and_(
            PerformanceReport.grant_id == grant_id,
            PerformanceReport.period_label == data.period_label,
        ))
    )
    existing = existing_result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    if existing:
        existing.submitted_at = now
        existing.submitted_by = user.id
        existing.narrative = data.narrative
    else:
        existing = PerformanceReport(
            tenant_id=user.tenant_id,
            grant_id=grant_id,
            period_label=data.period_label,
            period_end=now.date(),
            submitted_at=now,
            submitted_by=user.id,
            narrative=data.narrative,
        )
        db.add(existing)
    await db.commit()
    return {"period_label": data.period_label, "submitted_at": now.isoformat()}
