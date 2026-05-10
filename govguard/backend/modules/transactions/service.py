"""GovGuard™ — Transaction Service"""
import uuid
from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from core.cache import cache_get, cache_set, cache_delete_pattern
from core.exceptions import TransactionNotFound
from core.models import Transaction, RiskScoreLog
from modules.transactions.repository import TransactionRepository
from modules.transactions.schemas import (
    TransactionCreate, TransactionFlagUpdate, TransactionResponse,
    RiskScoreResponse, BulkUploadResponse, TransactionListResponse,
)

log = structlog.get_logger()


class TransactionService:
    def __init__(self, db: AsyncSession):
        self.repo = TransactionRepository(db)
        self.db = db

    async def create_transaction(
        self,
        data: TransactionCreate,
        tenant_id: UUID,
        user_id: UUID,
    ) -> TransactionResponse:
        """Create transaction, check for duplicates, queue async risk scoring."""

        # 1. Check for exact duplicate invoice
        dupes = await self.repo.check_duplicate_invoice(
            tenant_id, data.vendor_id, data.invoice_ref, data.amount
        )
        initial_status = "suppressed" if dupes else "pending"
        flag_reason = f"Duplicate of transaction {dupes[0].id}" if dupes else None

        # 2. Create transaction record
        tx = await self.repo.create(
            tenant_id=tenant_id,
            grant_id=data.grant_id,
            vendor_id=data.vendor_id,
            amount=data.amount,
            invoice_ref=data.invoice_ref,
            tx_date=data.tx_date,
            cost_category=data.cost_category,
        )
        if initial_status != "pending":
            await self.repo.update_risk_score(tx.id, Decimal("0"), initial_status, flag_reason)

        # 3. Queue async ML risk scoring (Celery)
        if initial_status == "pending":
            try:
                from workers.payment_tasks import score_transaction_async
                score_transaction_async.delay(str(tx.id), str(tenant_id))
            except Exception as e:
                log.warning("celery_dispatch_failed", error=str(e), tx_id=str(tx.id))

        # 4. Invalidate dashboard KPI cache
        await cache_delete_pattern(f"kpis:{tenant_id}:*")

        resp = TransactionResponse.model_validate(tx)
        resp.queued = True
        return resp

    async def get_risk_score(self, tx_id: UUID, tenant_id: UUID) -> RiskScoreResponse:
        tx = await self.repo.get(tx_id, tenant_id)
        if tx.risk_score is None:
            # Check Redis cache first
            cached = await cache_get(f"rs:{tx_id}")
            if cached:
                return RiskScoreResponse(**cached)
            return RiskScoreResponse(
                score=Decimal("0"),
                feature_weights={},
                model_version="pending",
                explanation="Risk scoring is in progress. Check back shortly.",
                is_high_risk=False,
            )

        log_entry = await self.repo.get_risk_score_log(tx_id)
        weights = log_entry.feature_weights_json if log_entry else {}
        model_ver = log_entry.model_version if log_entry else "unknown"

        score = float(tx.risk_score)
        explanation = self._generate_explanation(score, weights)

        result = RiskScoreResponse(
            score=tx.risk_score,
            feature_weights=weights,
            model_version=model_ver,
            explanation=explanation,
            is_high_risk=score >= 75.0,
        )
        await cache_set(f"rs:{tx_id}", result.model_dump(mode="json"), ttl=86400)
        return result

    async def flag_transaction(
        self,
        tx_id: UUID,
        tenant_id: UUID,
        data: TransactionFlagUpdate,
        reviewer_id: UUID,
    ) -> TransactionResponse:
        tx = await self.repo.update_flag(
            tx_id=tx_id,
            tenant_id=tenant_id,
            flag_status=data.flag_status,
            justification=data.justification,
            reviewer_id=reviewer_id,
        )
        await cache_delete_pattern(f"kpis:{tenant_id}:*")
        await cache_delete_pattern(f"rs:{tx_id}")
        return TransactionResponse.model_validate(tx)

    async def list_transactions(
        self,
        grant_id: Optional[UUID],
        tenant_id: UUID,
        flag_status: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        page: int = 1,
        limit: int = 50,
    ) -> TransactionListResponse:
        txns, total = await self.repo.list_by_grant(
            grant_id=grant_id,
            flag_status=flag_status,
            date_from=date_from,
            date_to=date_to,
            page=page,
            limit=limit,
        )
        return TransactionListResponse(
            transactions=[TransactionResponse.model_validate(t) for t in txns],
            total=total,
            page=page,
            limit=limit,
        )

    def _generate_explanation(self, score: float, weights: dict) -> str:
        if score >= 75:
            top = sorted(weights.items(), key=lambda x: abs(x[1]), reverse=True)[:3]
            factors = ", ".join(f"{k.replace('_', ' ')}" for k, v in top if v > 0)
            return f"HIGH RISK (score {score:.1f}/100). Primary factors: {factors or 'anomalous pattern'}."
        elif score >= 40:
            return f"MEDIUM RISK (score {score:.1f}/100). Monitor closely."
        return f"LOW RISK (score {score:.1f}/100). No significant anomalies detected."
