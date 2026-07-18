"""GovGuard™ — Tenants Module"""
from datetime import datetime
from uuid import UUID
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, func
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user_or_service as get_current_user, require_role, UserContext
from core.db import get_db
from core.models import Tenant, User, Grant


class TenantResponse(BaseModel):
    id: UUID
    name: str
    tier: int
    plan: str
    fedramp_scope: bool
    modules_enabled: list[str]
    created_at: datetime
    model_config = {"from_attributes": True}


router = APIRouter()


@router.get("")
async def list_tenants(
    user: UserContext = Depends(require_role("system_admin")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(select(Tenant).order_by(Tenant.created_at))
    tenants = result.scalars().all()

    ids = [t.id for t in tenants]
    user_counts: dict = {}
    grant_counts: dict = {}
    if ids:
        uc = await db.execute(
            select(User.tenant_id, func.count(User.id)).where(User.tenant_id.in_(ids)).group_by(User.tenant_id)
        )
        user_counts = dict(uc.all())
        gc = await db.execute(
            select(Grant.tenant_id, func.count(Grant.id)).where(Grant.tenant_id.in_(ids)).group_by(Grant.tenant_id)
        )
        grant_counts = dict(gc.all())

    return {
        "tenants": [
            {
                **TenantResponse.model_validate(t).model_dump(),
                "user_count": user_counts.get(t.id, 0),
                "grant_count": grant_counts.get(t.id, 0),
            }
            for t in tenants
        ],
        "total": len(tenants),
    }
