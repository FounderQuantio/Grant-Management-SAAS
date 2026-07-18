"""GovGuard™ — Erp Integration Module"""
from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user_or_service as get_current_user, require_role, UserContext
from core.db import get_db
from core.models import ERPSyncJob

router = APIRouter()


@router.get("/jobs")
async def list_sync_jobs(
    user: UserContext = Depends(require_role("compliance_officer")),
    db: AsyncSession = Depends(get_db),
):
    result = await db.execute(
        select(ERPSyncJob)
        .where(ERPSyncJob.tenant_id == user.tenant_id)
        .order_by(ERPSyncJob.created_at.desc())
        .limit(50)
    )
    jobs = result.scalars().all()
    return {
        "jobs": [
            {
                "id": str(j.id),
                "job_type": j.job_type,
                "status": j.status,
                "rows_total": j.rows_total,
                "rows_processed": j.rows_processed,
                "rows_failed": j.rows_failed,
                "started_at": j.started_at.isoformat() if j.started_at else None,
                "completed_at": j.completed_at.isoformat() if j.completed_at else None,
                "created_at": j.created_at.isoformat(),
            }
            for j in jobs
        ],
        "total": len(jobs),
    }
