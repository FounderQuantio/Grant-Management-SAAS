"""GovGuard™ — Dashboard Router"""
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user_or_service as get_current_user, UserContext
from core.db import get_db, set_tenant
from modules.dashboard.service import DashboardService

router = APIRouter()


async def _get_svc(
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> DashboardService:
    await set_tenant(db, str(user.tenant_id))
    return DashboardService(db)


@router.get("/kpis")
async def get_kpis(
    period: str = Query("30d"),
    user: UserContext = Depends(get_current_user),
    svc: DashboardService = Depends(_get_svc),
):
    days = int(period.rstrip("d")) if period.endswith("d") else 30
    return await svc.get_kpis(user.tenant_id, days)


@router.get("/heatmap")
async def get_heatmap(
    grant_id: Optional[UUID] = Query(None),
    group_by: str = Query("category"),
    period: str = Query("30d"),
    user: UserContext = Depends(get_current_user),
    svc: DashboardService = Depends(_get_svc),
):
    days = int(period.rstrip("d")) if period.endswith("d") else 30
    return await svc.get_heatmap(user.tenant_id, grant_id, group_by, days)


@router.get("/alerts")
async def get_alerts(
    limit: int = Query(50, ge=1, le=200),
    since: Optional[str] = Query(None),
    user: UserContext = Depends(get_current_user),
    svc: DashboardService = Depends(_get_svc),
):
    return await svc.get_alerts(user.tenant_id, limit, since)


@router.get("/ws-token")
async def get_ws_token(
    user: UserContext = Depends(get_current_user),
    svc: DashboardService = Depends(_get_svc),
):
    return await svc.get_ws_token(user.tenant_id, user.id)


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket, token: str, tenant_id: str):
    """Real-time alert feed via WebSocket. Forwards ALERT/KPI_UPDATE/
    COMPLIANCE_CHANGE/FRAUD_FLAG events published (see core.cache.publish_event)
    on the per-tenant Redis pub/sub channel, alongside a 30s PING heartbeat."""
    from core.cache import cache_get, redis_client
    import asyncio
    import json

    # Validate WS token (skip if Redis unavailable)
    if redis_client is not None:
        ctx = await cache_get(f"wst:{token}")
        if not ctx or ctx.get("tenant_id") != tenant_id:
            await websocket.close(code=4001)
            return

    await websocket.accept()
    send_lock = asyncio.Lock()

    async def heartbeat():
        ping_count = 0
        while True:
            await asyncio.sleep(30)
            ping_count += 1
            async with send_lock:
                await websocket.send_text(json.dumps({"type": "PING", "count": ping_count}))
            await asyncio.wait_for(websocket.receive_text(), timeout=10.0)

    async def event_listener():
        if redis_client is None:
            await asyncio.Event().wait()  # No pub/sub available; heartbeat-only connection.
            return
        channel = f"events:{tenant_id}"
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(channel)
        try:
            async for message in pubsub.listen():
                if message["type"] != "message":
                    continue
                async with send_lock:
                    await websocket.send_text(message["data"])
        finally:
            await pubsub.unsubscribe(channel)
            await pubsub.aclose()

    tasks = [asyncio.create_task(heartbeat()), asyncio.create_task(event_listener())]
    done, pending = await asyncio.wait(tasks, return_when=asyncio.FIRST_COMPLETED)
    for t in pending:
        t.cancel()
    await asyncio.gather(*pending, return_exceptions=True)
    for t in done:
        exc = t.exception()  # retrieve to avoid "exception never retrieved" warnings
        if exc and not isinstance(exc, (WebSocketDisconnect, asyncio.TimeoutError)):
            raise exc
    try:
        await websocket.close()
    except Exception:
        pass  # already closed by the client
