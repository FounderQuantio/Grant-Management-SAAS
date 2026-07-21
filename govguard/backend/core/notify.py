"""GovGuard™ — Durable notification + live pub/sub dispatch.

Persists a Notification row (so it survives a missed WebSocket connection --
the /notifications page reads this table) and publishes the same event over
Redis pub/sub (core.cache.publish_event) for the live dashboard feed. Only
call this for events a user should see in their notification history
(FRAUD_FLAG, COMPLIANCE_CHANGE, ALERT) -- high-frequency events like
KPI_UPDATE should keep calling publish_event() directly to avoid flooding
the inbox with routine noise.
"""
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from sqlalchemy.ext.asyncio import AsyncSession

from core.cache import publish_event
from core.models import Notification


async def notify(
    db: AsyncSession,
    tenant_id: UUID,
    *,
    ws_type: str,
    severity: str,
    title: str,
    body: Optional[str] = None,
    payload: Optional[dict] = None,
) -> None:
    ntype = "alert" if severity in ("critical", "warning") else "info"
    db.add(Notification(
        tenant_id=tenant_id, type=ntype, title=title, body=body, source_type=ws_type,
    ))
    await db.commit()
    await publish_event(tenant_id, {
        "type": ws_type,
        "severity": severity,
        "payload": payload or {},
        "ts": datetime.now(timezone.utc).isoformat(),
    })
