"""GovGuard™ — Transactions Router"""
from datetime import date
from typing import Optional
from uuid import UUID

from fastapi import APIRouter, Depends, Query, UploadFile, File
from sqlalchemy.ext.asyncio import AsyncSession

from core.auth import get_current_user, require_role, UserContext
from core.db import get_db, set_tenant
from modules.transactions.schemas import (
    TransactionCreate, TransactionFlagUpdate,
    TransactionResponse, RiskScoreResponse,
    BulkUploadResponse, TransactionListResponse,
)
from modules.transactions.service import TransactionService

router = APIRouter()


async def _get_service(
    db: AsyncSession = Depends(get_db),
    user: UserContext = Depends(get_current_user),
) -> TransactionService:
    await set_tenant(db, str(user.tenant_id))
    return TransactionService(db)


@router.post("", response_model=TransactionResponse, status_code=202)
async def create_transaction(
    data: TransactionCreate,
    user: UserContext = Depends(require_role("finance_manager")),
    svc: TransactionService = Depends(_get_service),
):
    """Submit a transaction for risk scoring and compliance validation."""
    return await svc.create_transaction(data, user.tenant_id, user.id)


@router.post("/bulk", response_model=BulkUploadResponse, status_code=202)
async def bulk_upload_transactions(
    file: UploadFile = File(...),
    user: UserContext = Depends(require_role("finance_manager")),
    db: AsyncSession = Depends(get_db),
):
    """Bulk import transactions from CSV file."""
    from core.exceptions import FileTooLarge, ValidationError
    import uuid

    if file.size and file.size > 50 * 1024 * 1024:
        raise FileTooLarge()
    if not file.filename.endswith(".csv"):
        raise ValidationError("Only CSV files are accepted")

    await set_tenant(db, str(user.tenant_id))

    # Queue CSV ETL job
    try:
        from workers.sync_tasks import erp_csv_etl
        job_id = uuid.uuid4()
        # In production: save file to S3 first, then queue
        erp_csv_etl.delay(str(job_id), str(user.tenant_id), file.filename)
        return BulkUploadResponse(job_id=job_id, queued_count=0)
    except Exception:
        return BulkUploadResponse(job_id=uuid.uuid4(), queued_count=0)


@router.get("", response_model=TransactionListResponse)
async def list_transactions(
    grant_id: Optional[UUID] = Query(None),
    flag_status: Optional[str] = Query(None),
    date_from: Optional[date] = Query(None),
    date_to: Optional[date] = Query(None),
    page: int = Query(1, ge=1),
    limit: int = Query(50, ge=1, le=200),
    user: UserContext = Depends(require_role("finance_staff")),
    svc: TransactionService = Depends(_get_service),
):
    return await svc.list_transactions(
        grant_id=grant_id,
        tenant_id=user.tenant_id,
        flag_status=flag_status,
        date_from=date_from,
        date_to=date_to,
        page=page,
        limit=limit,
    )


@router.get("/{tx_id}/risk", response_model=RiskScoreResponse)
async def get_risk_score(
    tx_id: UUID,
    user: UserContext = Depends(get_current_user),
    svc: TransactionService = Depends(_get_service),
):
    return await svc.get_risk_score(tx_id, user.tenant_id)


@router.patch("/{tx_id}/flag", response_model=TransactionResponse)
async def flag_transaction(
    tx_id: UUID,
    data: TransactionFlagUpdate,
    user: UserContext = Depends(require_role("finance_manager")),
    svc: TransactionService = Depends(_get_service),
):
    return await svc.flag_transaction(tx_id, user.tenant_id, data, user.id)
