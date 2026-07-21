"""GovGuard™ — Notifications Module

Durable notification history backing the frontend's /notifications page.
Rows are created by core.notify.notify() alongside the live Redis pub/sub
event pushed to the dashboard WebSocket (see modules/dashboard/router.py),
so a notification is visible here even if the user was offline when it fired.
"""
from datetime import datetime, timezone
from fastapi import APIRouter, Depends
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user_or_service as get_current_user, UserContext
from core.db import get_db, set_tenant
from core.models import Notification

router = APIRouter()


@router.get("")
async def list_notifications(
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await set_tenant(db, str(user.tenant_id))
    result = await db.execute(
        select(Notification)
        .where(Notification.tenant_id == user.tenant_id)
        .order_by(Notification.created_at.desc())
        .limit(50)
    )
    rows = result.scalars().all()
    return {
        "notifications": [
            {
                "id": str(n.id),
                "type": n.type,
                "title": n.title,
                "body": n.body,
                "created_at": n.created_at.isoformat(),
                "read": n.read_at is not None,
            }
            for n in rows
        ],
    }


@router.post("/read-all")
async def mark_all_read(
    user: UserContext = Depends(get_current_user),
    db: AsyncSession = Depends(get_db),
):
    await set_tenant(db, str(user.tenant_id))
    now = datetime.now(timezone.utc)
    result = await db.execute(
        update(Notification)
        .where(Notification.tenant_id == user.tenant_id, Notification.read_at.is_(None))
        .values(read_at=now)
    )
    await db.commit()
    return {"marked_read": result.rowcount}
