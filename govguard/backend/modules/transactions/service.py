"""GovGuard™ — Transaction Service"""
import uuid
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy.ext.asyncio import AsyncSession

from core.cache import cache_get, cache_set, cache_delete_pattern, publish_event
from core.notify import notify
from core.exceptions import TransactionNotFound
from core.models import Transaction, RiskScoreLog
from modules.transactions.repository import TransactionRepository
from modules.transactions.schemas import (
    TransactionCreate, TransactionFlagUpdate, TransactionResponse,
    RiskScoreResponse, FraudAssessmentResponse, BulkUploadResponse, TransactionListResponse,
)
from services.fraud_detection.engine import FraudDetectionEngine
from services.fraud_detection.context_signals import get_related_party_flag
from services.anomaly_detection.processor import AnomalyDetectionProcessor

_fraud_engine = FraudDetectionEngine()
_anomaly_processor = AnomalyDetectionProcessor()

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
        """Create transaction, run fraud + anomaly engines, persist results."""

        # 1. Check for exact duplicate invoice
        dupes = await self.repo.check_duplicate_invoice(
            tenant_id, data.vendor_id, data.invoice_ref, data.amount
        )
        if dupes:
            tx = await self.repo.create(
                tenant_id=tenant_id, grant_id=data.grant_id,
                vendor_id=data.vendor_id, amount=data.amount,
                invoice_ref=data.invoice_ref, tx_date=data.tx_date,
                cost_category=data.cost_category,
            )
            await self.repo.update_risk_score(
                tx.id, Decimal("0"), "suppressed",
                f"Duplicate of transaction {dupes[0].id}"
            )
            await cache_delete_pattern(f"kpis:{tenant_id}:*")
            await publish_event(tenant_id, {
                "type": "KPI_UPDATE", "severity": "info",
                "payload": {"grant_id": str(data.grant_id), "reason": "duplicate_suppressed"},
                "ts": datetime.now(timezone.utc).isoformat(),
            })
            resp = TransactionResponse.model_validate(tx)
            resp.queued = False
            return resp

        # 2. Create transaction record
        tx = await self.repo.create(
            tenant_id=tenant_id, grant_id=data.grant_id,
            vendor_id=data.vendor_id, amount=data.amount,
            invoice_ref=data.invoice_ref, tx_date=data.tx_date,
            cost_category=data.cost_category,
        )

        # 3. Fetch context for fraud + anomaly engines
        vendor       = await self.repo.get_vendor(data.vendor_id)
        prior        = await self.repo.get_prior_invoices(data.vendor_id, tenant_id)
        spend_30d    = await self.repo.get_vendor_spend_30d(data.vendor_id, tenant_id)
        charges      = await self.repo.get_cross_grant_charges(data.vendor_id, data.cost_category, tenant_id)
        history      = await self.repo.get_historical_txns(data.grant_id)

        sam_status   = (vendor.sam_status if vendor else "unknown")
        risk_tier_v  = (vendor.risk_tier  if vendor else "medium")

        # Fetch grant for budget
        from core.models import Grant
        grant = await self.db.get(Grant, data.grant_id)
        budget = dict(grant.budget_json) if grant else {data.cost_category: float(data.amount) * 2}

        # 4. Run FraudDetectionEngine (synchronous, fast)
        related_party_flag = await get_related_party_flag(self.db, tenant_id, data.vendor_id)
        assessment = _fraud_engine.assess(
            transaction_id=str(tx.id),
            amount=float(data.amount),
            vendor_id=str(data.vendor_id),
            vendor_sam_status=sam_status,
            invoice_ref=data.invoice_ref,
            tx_date=data.tx_date,
            cost_category=data.cost_category,
            grant_budget=budget,
            prior_invoices=prior,
            vendor_spend_30d=spend_30d,
            all_grant_charges=charges,
            vendor_risk_tier=risk_tier_v,
            related_party_flag=related_party_flag,
        )

        await self.repo.create_fraud_assessment(
            tenant_id=tenant_id,
            transaction_id=tx.id,
            composite_score=assessment.composite_score,
            risk_tier=assessment.risk_tier,
            triggered_rules=assessment.triggered_rules,
            recommended_action=assessment.recommended_action,
            gao_references=assessment.gao_references,
            explanation=assessment.explanation,
            signal_detail=assessment.to_dict()["signal_detail"],
        )

        # 5. Run AnomalyDetectionProcessor
        current_tx_dict = {
            "amount": float(data.amount), "tx_date": data.tx_date,
            "vendor_id": str(data.vendor_id), "cost_category": data.cost_category,
        }
        anomaly_alerts = _anomaly_processor.detect(
            grant_id=str(data.grant_id),
            tenant_id=str(tenant_id),
            current_tx=current_tx_dict,
            historical_txns=history,
            grant_budget=budget,
            grant_total_amount=float(grant.total_amount) if grant else float(data.amount) * 10,
        )
        for alert in anomaly_alerts:
            await self.repo.create_anomaly_alert(
                tenant_id=tenant_id,
                grant_id=data.grant_id,
                anomaly_type=alert.anomaly_type,
                severity=alert.severity,
                score=float(alert.score),
                threshold=float(alert.threshold),
                observed_value=float(alert.observed_value) if alert.observed_value is not None else None,
                description=alert.description,
                gao_reference=alert.gao_reference,
                auto_action=alert.auto_action,
            )

        # 6. Update transaction risk score and flag status
        fraud_score = Decimal(str(round(assessment.composite_score, 2)))
        action = assessment.recommended_action
        flag_map = {"BLOCK": "flagged", "HOLD": "flagged", "REVIEW": "flagged", "APPROVE": "clear"}
        flag_status = flag_map.get(action, "pending")
        flag_reason = assessment.explanation if action != "APPROVE" else None
        await self.repo.update_risk_score(tx.id, fraud_score, flag_status, flag_reason)

        # 7. Queue ML risk scoring (Celery) — enriches risk_score_logs with IsolationForest score
        try:
            from workers.payment_tasks import score_transaction_async
            score_transaction_async.delay(str(tx.id), str(tenant_id))
        except Exception as e:
            log.warning("celery_dispatch_failed", error=str(e), tx_id=str(tx.id))

        await self.db.commit()
        await cache_delete_pattern(f"kpis:{tenant_id}:*")

        now_iso = datetime.now(timezone.utc).isoformat()
        await publish_event(tenant_id, {
            "type": "KPI_UPDATE", "severity": "info",
            "payload": {"grant_id": str(data.grant_id), "transaction_id": str(tx.id)},
            "ts": now_iso,
        })
        if flag_status == "flagged":
            await notify(
                self.db, tenant_id,
                ws_type="FRAUD_FLAG",
                severity="critical" if fraud_score >= 75 else "warning",
                title=f"Transaction flagged for review (risk {fraud_score:.0f}/100)",
                body=f"${data.amount:,.2f} — invoice {data.invoice_ref} — recommended action: {action}",
                payload={
                    "transaction_id": str(tx.id), "grant_id": str(data.grant_id),
                    "risk_score": float(fraud_score), "action": action,
                },
            )

        resp = TransactionResponse.model_validate(tx)
        resp.queued = True
        return resp

    async def get_fraud_assessment(self, tx_id: UUID, tenant_id: UUID) -> FraudAssessmentResponse:
        fa = await self.repo.get_fraud_assessment(tx_id)
        if not fa:
            from core.exceptions import TransactionNotFound
            raise TransactionNotFound()
        return FraudAssessmentResponse(
            transaction_id=fa.transaction_id,
            composite_score=fa.composite_score,
            risk_tier=fa.risk_tier,
            triggered_rules=fa.triggered_rules,
            recommended_action=fa.recommended_action,
            gao_references=fa.gao_references,
            explanation=fa.explanation,
            signal_detail=fa.signal_detail,
            engine_version=fa.engine_version,
            created_at=fa.created_at,
        )

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
        await notify(
            self.db, tenant_id,
            ws_type="FRAUD_FLAG" if data.flag_status == "flagged" else "ALERT",
            severity="critical" if data.flag_status == "flagged" else "info",
            title=f"Transaction marked {data.flag_status}",
            body=data.justification,
            payload={"transaction_id": str(tx_id), "flag_status": data.flag_status},
        )
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
