"""GovGuard™ — Users Module"""
from datetime import datetime
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy import select, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import require_role, UserContext
from core.db import get_db, set_tenant
from core.models import User
from core.exceptions import NotFoundError


class UserResponse(BaseModel):
    id: UUID
    display_name: str
    role: str
    mfa_enabled: bool
    is_active: bool
    last_login: Optional[datetime]
    created_at: datetime
    model_config = {"from_attributes": True}


class UserUpdate(BaseModel):
    display_name: Optional[str] = None
    role: Optional[str] = None
    is_active: Optional[bool] = None


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


@router.patch("/{user_id}")
async def update_user(
    user_id: UUID,
    data: UserUpdate,
    user: UserContext = Depends(require_role("compliance_officer")),
    db: AsyncSession = Depends(get_db),
):
    await set_tenant(db, str(user.tenant_id))
    result = await db.execute(
        select(User).where(and_(User.id == user_id, User.tenant_id == user.tenant_id))
    )
    target = result.scalar_one_or_none()
    if not target:
        raise NotFoundError("User not found")

    if data.display_name is not None:
        target.display_name = data.display_name
    if data.role is not None:
        target.role = data.role
    if data.is_active is not None:
        target.is_active = data.is_active

    await db.commit()
    return UserResponse.model_validate(target).model_dump()
