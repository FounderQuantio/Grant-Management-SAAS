"""GovGuard™ — Safe resolution of a UserContext.id for FK columns referencing
users.id. The demo/service-secret auth path (see core.auth.get_current_user_or_service)
defaults to a synthetic user id that does not correspond to any real row in
the users table, which trips foreign-key constraints on INSERT. Real Cognito
sessions always resolve to a genuine users.id. Falls back to NULL rather than
failing the request when the id isn't a real row."""
from typing import Optional
from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.models import User


async def resolve_user_fk(db: AsyncSession, user_id: UUID) -> Optional[UUID]:
    result = await db.execute(select(User.id).where(User.id == user_id))
    return result.scalar_one_or_none()
