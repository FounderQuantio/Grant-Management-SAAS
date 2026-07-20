"""GovGuard™ — Budget Modification Prior-Approval Workflow (2 CFR 200.308)

2 CFR 200.308(e)(3): cumulative transfers among direct cost categories that
exceed 10% of the total approved budget require prior written approval from
the federal awarding agency before the recipient may implement the change.

This module enforces that gate in the request itself: modifications under
the cumulative 10% threshold apply immediately; modifications that cross it
are held as pending until a compliance_officer/system_admin approves them —
the underlying budget_json is not touched until approval.
"""
from datetime import datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user_or_service as get_current_user, require_role, UserContext
from core.db import get_db, set_tenant
from core.models import Grant, BudgetModificationRequest
from core.exceptions import GrantNotFound, NotFoundError
from core.user_fk import resolve_user_fk

router = APIRouter()

PRIOR_APPROVAL_THRESHOLD_PCT = Decimal("10.0")


class ModificationRequest(BaseModel):
    category: str
    new_amount: float


class ModificationReview(BaseModel):
    approve: bool
    note: Optional[str] = None


async def _cumulative_modification_pct(db: AsyncSession, grant_id: UUID, tenant_id: UUID) -> Decimal:
    """Sum of absolute delta_amount across all resolved (approved/auto_applied)
    modifications to date for this grant, as a % of the grant's total_amount."""
    result = await db.execute(
        select(func.coalesce(func.sum(func.abs(BudgetModificationRequest.delta_amount)), 0)).where(
            and_(
                BudgetModificationRequest.grant_id == grant_id,
                BudgetModificationRequest.tenant_id == tenant_id,
                BudgetModificationRequest.status.in_(["approved", "auto_applied"]),
            )
        )
    )
    cumulative_delta = result.scalar() or Decimal("0")
    return cumulative_delta


@router.get("/grants/{grant_id}")
async def list_modifications(
    grant_id: UUID,
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await set_tenant(db, str(user.tenant_id))
    result = await db.execute(
        select(BudgetModificationRequest)
        .where(and_(BudgetModificationRequest.grant_id == grant_id, BudgetModificationRequest.tenant_id == user.tenant_id))
        .order_by(BudgetModificationRequest.created_at.desc())
    )
    mods = result.scalars().all()
    return {
        "grant_id": str(grant_id),
        "modifications": [
            {
                "id": str(m.id),
                "category": m.category,
                "old_amount": float(m.old_amount),
                "new_amount": float(m.new_amount),
                "delta_amount": float(m.delta_amount),
                "cumulative_pct_of_total": float(m.cumulative_pct_of_total),
                "requires_prior_approval": m.requires_prior_approval,
                "status": m.status,
                "reviewed_at": m.reviewed_at.isoformat() if m.reviewed_at else None,
                "created_at": m.created_at.isoformat(),
            }
            for m in mods
        ],
    }


@router.post("/grants/{grant_id}", status_code=201)
async def request_modification(
    grant_id: UUID,
    data: ModificationRequest,
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

    budget = dict(grant.budget_json or {})
    old_amount = Decimal(str(budget.get(data.category, 0)))
    new_amount = Decimal(str(data.new_amount))
    delta = new_amount - old_amount

    prior_cumulative = await _cumulative_modification_pct(db, grant_id, user.tenant_id)
    total_amount = Decimal(str(grant.total_amount)) or Decimal("1")
    projected_cumulative_pct = ((prior_cumulative + abs(delta)) / total_amount) * 100
    requires_approval = projected_cumulative_pct >= PRIOR_APPROVAL_THRESHOLD_PCT

    mod = BudgetModificationRequest(
        tenant_id=user.tenant_id,
        grant_id=grant_id,
        category=data.category,
        old_amount=old_amount,
        new_amount=new_amount,
        delta_amount=delta,
        cumulative_pct_of_total=projected_cumulative_pct,
        requires_prior_approval=requires_approval,
        status="pending" if requires_approval else "auto_applied",
        requested_by=await resolve_user_fk(db, user.id),
    )
    db.add(mod)

    if not requires_approval:
        budget[data.category] = float(new_amount)
        grant.budget_json = budget

    await db.commit()
    await db.refresh(mod)
    return {
        "id": str(mod.id),
        "status": mod.status,
        "requires_prior_approval": requires_approval,
        "cumulative_pct_of_total": float(projected_cumulative_pct),
    }


@router.patch("/{mod_id}/review")
async def review_modification(
    mod_id: UUID,
    data: ModificationReview,
    user: UserContext = Depends(require_role("compliance_officer")),
    db: AsyncSession = Depends(get_db),
):
    await set_tenant(db, str(user.tenant_id))
    result = await db.execute(
        select(BudgetModificationRequest).where(
            and_(BudgetModificationRequest.id == mod_id, BudgetModificationRequest.tenant_id == user.tenant_id)
        )
    )
    mod = result.scalar_one_or_none()
    if not mod:
        raise NotFoundError("Budget modification request not found")
    if mod.status != "pending":
        raise NotFoundError(f"Request already resolved (status={mod.status})")

    mod.reviewed_by = await resolve_user_fk(db, user.id)
    mod.reviewed_at = datetime.now(timezone.utc)
    mod.review_note = data.note

    if data.approve:
        mod.status = "approved"
        grant_result = await db.execute(
            select(Grant).where(and_(Grant.id == mod.grant_id, Grant.tenant_id == user.tenant_id))
        )
        grant = grant_result.scalar_one_or_none()
        if grant:
            budget = dict(grant.budget_json or {})
            budget[mod.category] = float(mod.new_amount)
            grant.budget_json = budget
    else:
        mod.status = "rejected"

    await db.commit()
    return {"id": str(mod.id), "status": mod.status}
