"""GovGuard™ — Compliance Router"""
from typing import Optional
from uuid import UUID
from fastapi import APIRouter, Depends, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user, require_role, UserContext
from core.db import get_db, set_tenant
from modules.compliance_engine.schemas import (
    ControlListResponse, ControlUpdate, ControlResponse,
    ComplianceRunRequest, ComplianceRunResponse, SoDResponse,
)
from modules.compliance_engine.service import ComplianceService

router = APIRouter()


async def _get_svc(
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> ComplianceService:
    await set_tenant(db, str(user.tenant_id))
    return ComplianceService(db)


@router.get("/controls", response_model=ControlListResponse)
async def list_controls(
    grant_id: Optional[UUID] = Query(None),
    status: Optional[str] = Query(None),
    domain: Optional[str] = Query(None),
    user: UserContext = Depends(get_current_user),
    svc: ComplianceService = Depends(_get_svc),
):
    return await svc.list_controls(user.tenant_id, grant_id, status, domain)


@router.patch("/controls/{control_id}", response_model=ControlResponse)
async def update_control(
    control_id: UUID,
    data: ControlUpdate,
    user: UserContext = Depends(require_role("compliance_officer")),
    svc: ComplianceService = Depends(_get_svc),
):
    return await svc.update_control(control_id, user.tenant_id, data)


@router.post("/controls/{control_id}/evidence")
async def upload_evidence(
    control_id: UUID,
    file: UploadFile = File(...),
    user: UserContext = Depends(require_role("compliance_officer")),
    db: AsyncSession = Depends(get_db),
):
    from core.exceptions import FileTooLarge
    from core.s3 import upload_evidence, get_presigned_url
    from core.settings import settings

    if file.size and file.size > 50 * 1024 * 1024:
        raise FileTooLarge()

    await set_tenant(db, str(user.tenant_id))
    s3_key = await upload_evidence(str(user.tenant_id), str(control_id), file)
    view_url = await get_presigned_url(settings.S3_EVIDENCE_BUCKET, s3_key, expires=900)

    # Update control record
    from core.models import ComplianceControl
    from sqlalchemy import select, and_
    result = await db.execute(
        select(ComplianceControl).where(
            and_(ComplianceControl.id == control_id, ComplianceControl.tenant_id == user.tenant_id)
        )
    )
    ctrl = result.scalar_one_or_none()
    if ctrl:
        ctrl.evidence_s3_key = s3_key
        await db.commit()

    return {"evidence_s3_key": s3_key, "presigned_view_url": view_url, "expires_in": 900}


@router.get("/sod", response_model=SoDResponse)
async def check_sod(
    user_id: Optional[UUID] = Query(None),
    user: UserContext = Depends(require_role("finance_manager")),
    svc: ComplianceService = Depends(_get_svc),
):
    return await svc.check_sod(user.tenant_id, user_id)


@router.post("/run", response_model=ComplianceRunResponse, status_code=202)
async def run_compliance(
    data: ComplianceRunRequest,
    user: UserContext = Depends(require_role("compliance_officer")),
    svc: ComplianceService = Depends(_get_svc),
):
    return await svc.run_compliance_check(data, user.tenant_id)
