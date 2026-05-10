"""GovGuard™ — Dashboard Router"""
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, WebSocket, WebSocketDisconnect
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user, UserContext
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
    user: UserContext = Depends(get_current_user),
    svc: DashboardService = Depends(_get_svc),
):
    return await svc.get_heatmap(user.tenant_id, grant_id, group_by)


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
    """Real-time alert feed via WebSocket."""
    from core.cache import cache_get
    import asyncio
    import json

    # Validate WS token
    ctx = await cache_get(f"wst:{token}")
    if not ctx or ctx.get("tenant_id") != tenant_id:
        await websocket.close(code=4001)
        return

    await websocket.accept()
    try:
        ping_count = 0
        while True:
            # Heartbeat every 30s
            await asyncio.sleep(30)
            ping_count += 1
            await websocket.send_text(json.dumps({"type": "PING", "count": ping_count}))
            try:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=10.0)
            except asyncio.TimeoutError:
                await websocket.close(code=4000)
                break
    except WebSocketDisconnect:
        pass
