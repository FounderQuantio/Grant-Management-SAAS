"""GovGuard™ — Users Module"""
from datetime import datetime
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user_or_service as get_current_user, require_role, UserContext
from core.db import get_db, set_tenant
from core.models import User


class UserResponse(BaseModel):
    id: UUID
    display_name: str
    role: str
    mfa_enabled: bool
    is_active: bool
    last_login: Optional[datetime]
    created_at: datetime
    model_config = {"from_attributes": True}


router = APIRouter()


@router.get("")
async def list_users(
    user: UserContext = Depends(require_role("compliance_officer")),
    db: AsyncSession = Depends(get_db),
):
    await set_tenant(db, str(user.tenant_id))
    result = await db.execute(select(User).where(User.tenant_id == user.tenant_id).order_by(User.created_at))
    users = result.scalars().all()
    return {
        "users": [UserResponse.model_validate(u).model_dump() for u in users],
        "total": len(users),
    }
