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
from core.exceptions import GrantNotFound, ValidationError
from core.user_fk import resolve_user_fk
from modules.performance_reporting.service import expected_quarterly_periods

router = APIRouter()

# 2 CFR 200.415(a) — the exact required certification language.
CERTIFICATION_TEXT = (
    "By signing this report, I certify to the best of my knowledge and belief "
    "that the report is true, complete, and accurate, and the expenditures, "
    "disbursements and cash receipts are for the purposes and objectives set "
    "forth in the terms and conditions of the Federal award. I am aware that "
    "any false, fictitious, or fraudulent information, or the omission of any "
    "material fact, may subject me to criminal, civil or administrative "
    "penalties for fraud, false statements, false claims or otherwise "
    "(18 U.S.C. 1001 and 31 U.S.C. 3729-3730 and 3801-3812)."
)


class ReportSubmit(BaseModel):
    period_label: str
    narrative: Optional[str] = None
    certification_accepted: bool = False


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
            "certification_accepted": sub.certification_accepted if sub else None,
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
    if not data.certification_accepted:
        raise ValidationError(
            "2 CFR 200.415 requires a signed certification to submit a performance report. "
            "Set certification_accepted=true to attest to the required statement."
        )

    await set_tenant(db, str(user.tenant_id))
    result = await db.execute(
        select(Grant).where(and_(Grant.id == grant_id, Grant.tenant_id == user.tenant_id))
    )
    grant = result.scalar_one_or_none()
    if not grant:
        raise GrantNotFound()

    matching_period = next(
        (p for p in expected_quarterly_periods(grant.period_start, grant.period_end)
         if p["label"] == data.period_label),
        None,
    )
    period_end = matching_period["period_end"] if matching_period else date.today()

    existing_result = await db.execute(
        select(PerformanceReport).where(and_(
            PerformanceReport.grant_id == grant_id,
            PerformanceReport.period_label == data.period_label,
        ))
    )
    existing = existing_result.scalar_one_or_none()
    now = datetime.now(timezone.utc)
    submitted_by = await resolve_user_fk(db, user.id)
    if existing:
        existing.submitted_at = now
        existing.submitted_by = submitted_by
        existing.narrative = data.narrative
        existing.certification_accepted = True
        existing.certification_text = CERTIFICATION_TEXT
    else:
        existing = PerformanceReport(
            tenant_id=user.tenant_id,
            grant_id=grant_id,
            period_label=data.period_label,
            period_end=period_end,
            submitted_at=now,
            submitted_by=submitted_by,
            narrative=data.narrative,
            certification_accepted=True,
            certification_text=CERTIFICATION_TEXT,
        )
        db.add(existing)
    await db.commit()
    return {
        "period_label": data.period_label,
        "submitted_at": now.isoformat(),
        "certification_accepted": True,
    }
