"""GovGuard™ — Tool Downloads Module
Tracks document download events for NIW petition tools.
Public endpoints — no auth required (counters are public-facing).
"""
import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel
from sqlalchemy import select, func, text
from sqlalchemy.ext.asyncio import AsyncSession

from core.db import get_db

router = APIRouter()


# ── Schemas ───────────────────────────────────────────────────────────────

class DownloadCountResponse(BaseModel):
    tool_id: str
    count: int


class DownloadRecordResponse(BaseModel):
    tool_id: str
    count: int
    recorded: bool


# ── Endpoints ─────────────────────────────────────────────────────────────

@router.post("/{tool_id}", response_model=DownloadRecordResponse)
async def record_download(
    tool_id: str,
    request: Request,
    db: AsyncSession = Depends(get_db),
):
    """Log a download event and return the updated total count."""
    user_agent = request.headers.get("user-agent", "")[:500]

    await db.execute(
        text(
            "INSERT INTO tool_downloads (id, tool_id, downloaded_at, user_agent) "
            "VALUES (:id, :tool_id, :ts, :ua)"
        ),
        {
            "id": str(uuid.uuid4()),
            "tool_id": tool_id,
            "ts": datetime.now(timezone.utc),
            "ua": user_agent,
        },
    )
    await db.commit()

    result = await db.execute(
        text("SELECT COUNT(*) FROM tool_downloads WHERE tool_id = :tool_id"),
        {"tool_id": tool_id},
    )
    count = result.scalar_one()

    return DownloadRecordResponse(tool_id=tool_id, count=int(count), recorded=True)


@router.get("/{tool_id}", response_model=DownloadCountResponse)
async def get_download_count(
    tool_id: str,
    db: AsyncSession = Depends(get_db),
):
    """Return the total download count for a tool."""
    result = await db.execute(
        text("SELECT COUNT(*) FROM tool_downloads WHERE tool_id = :tool_id"),
        {"tool_id": tool_id},
    )
    count = result.scalar_one()
    return DownloadCountResponse(tool_id=tool_id, count=int(count))
