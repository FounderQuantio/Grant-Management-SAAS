"""GovGuard™ — Transaction Repository"""
import uuid
from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import text

from datetime import timedelta
from sqlalchemy import text as sa_text
from core.models import Transaction, Grant, Vendor, RiskScoreLog, FraudAssessmentLog, AnomalyAlert
from core.exceptions import TransactionNotFound, GrantNotFound


class TransactionRepository:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def create(
        self,
        tenant_id: UUID,
        grant_id: UUID,
        vendor_id: UUID,
        amount: Decimal,
        invoice_ref: str,
        tx_date: date,
        cost_category: str,
    ) -> Transaction:
        """Insert a new transaction. Validates budget category before insert."""
        # Validate cost_category against grant budget
        grant = await self.db.get(Grant, grant_id)
        if not grant:
            raise GrantNotFound()
        if grant.status != "active":
            from core.exceptions import ValidationError
            raise ValidationError("Cannot add transactions to a non-active grant")
        if cost_category not in grant.budget_json:
            from core.exceptions import ValidationError
            raise ValidationError(
                f"cost_category '{cost_category}' not in grant budget structure",
                details={"allowed": list(grant.budget_json.keys())},
            )

        tx = Transaction(
            id=uuid.uuid4(),
            tenant_id=tenant_id,
            grant_id=grant_id,
            vendor_id=vendor_id,
            amount=amount,
            invoice_ref=invoice_ref,
            tx_date=tx_date,
            cost_category=cost_category,
            flag_status="pending",
        )
        self.db.add(tx)
        await self.db.commit()
        await self.db.refresh(tx)
        return tx

    async def get(self, tx_id: UUID, tenant_id: UUID) -> Transaction:
        result = await self.db.execute(
            select(Transaction).where(
                and_(Transaction.id == tx_id, Transaction.tenant_id == tenant_id)
            )
        )
        tx = result.scalar_one_or_none()
        if not tx:
            raise TransactionNotFound()
        return tx

    async def list_by_grant(
        self,
        grant_id: UUID,
        flag_status: Optional[str] = None,
        date_from: Optional[date] = None,
        date_to: Optional[date] = None,
        page: int = 1,
        limit: int = 50,
    ) -> tuple[list[Transaction], int]:
        q = select(Transaction).where(Transaction.grant_id == grant_id)
        if flag_status:
            q = q.where(Transaction.flag_status == flag_status)
        if date_from:
            q = q.where(Transaction.tx_date >= date_from)
        if date_to:
            q = q.where(Transaction.tx_date <= date_to)

        count_q = select(func.count()).select_from(q.subquery())
        total = await self.db.scalar(count_q) or 0
        result = await self.db.execute(q.offset((page - 1) * limit).limit(limit))
        return result.scalars().all(), total

    async def update_flag(
        self,
        tx_id: UUID,
        tenant_id: UUID,
        flag_status: str,
        justification: str,
        reviewer_id: UUID,
    ) -> Transaction:
        tx = await self.get(tx_id, tenant_id)
        tx.flag_status = flag_status
        tx.flag_reason = justification
        tx.reviewed_by = reviewer_id
        from datetime import datetime, timezone
        tx.reviewed_at = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(tx)
        return tx

    async def update_risk_score(
        self,
        tx_id: UUID,
        score: Decimal,
        flag_status: str,
        flag_reason: str,
    ) -> None:
        await self.db.execute(
            update(Transaction)
            .where(Transaction.id == tx_id)
            .values(risk_score=score, flag_status=flag_status, flag_reason=flag_reason)
        )
        await self.db.commit()

    async def get_risk_score_log(self, tx_id: UUID) -> Optional[RiskScoreLog]:
        result = await self.db.execute(
            select(RiskScoreLog)
            .where(RiskScoreLog.transaction_id == tx_id)
            .order_by(RiskScoreLog.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def get_vendor(self, vendor_id: UUID) -> Optional[Vendor]:
        return await self.db.get(Vendor, vendor_id)

    async def get_prior_invoices(self, vendor_id: UUID, tenant_id: UUID, limit: int = 20) -> list[dict]:
        result = await self.db.execute(
            select(Transaction)
            .where(and_(Transaction.vendor_id == vendor_id, Transaction.tenant_id == tenant_id))
            .order_by(Transaction.tx_date.desc())
            .limit(limit)
        )
        return [
            {"id": str(t.id), "invoice_ref": t.invoice_ref,
             "amount": float(t.amount), "vendor_id": str(t.vendor_id),
             "tx_date": str(t.tx_date)}
            for t in result.scalars().all()
        ]

    async def get_vendor_spend_30d(self, vendor_id: UUID, tenant_id: UUID) -> float:
        cutoff = date.today() - timedelta(days=30)
        result = await self.db.execute(
            select(func.sum(Transaction.amount)).where(
                and_(Transaction.vendor_id == vendor_id,
                     Transaction.tenant_id == tenant_id,
                     Transaction.tx_date >= cutoff)
            )
        )
        return float(result.scalar() or 0)

    async def get_cross_grant_charges(
        self, vendor_id: UUID, cost_category: str, tenant_id: UUID
    ) -> list[dict]:
        result = await self.db.execute(
            select(Transaction)
            .where(and_(Transaction.vendor_id == vendor_id,
                        Transaction.cost_category == cost_category,
                        Transaction.tenant_id == tenant_id))
            .limit(50)
        )
        return [
            {"grant_id": str(t.grant_id), "cost_category": t.cost_category,
             "vendor_id": str(t.vendor_id)}
            for t in result.scalars().all()
        ]

    async def get_historical_txns(self, grant_id: UUID, days: int = 90) -> list[dict]:
        cutoff = date.today() - timedelta(days=days)
        result = await self.db.execute(
            select(Transaction)
            .where(and_(Transaction.grant_id == grant_id, Transaction.tx_date >= cutoff))
            .order_by(Transaction.tx_date.asc())
        )
        return [
            {"amount": float(t.amount), "tx_date": t.tx_date,
             "vendor_id": str(t.vendor_id), "cost_category": t.cost_category}
            for t in result.scalars().all()
        ]

    async def create_fraud_assessment(
        self,
        tenant_id: UUID,
        transaction_id: UUID,
        composite_score: float,
        risk_tier: str,
        triggered_rules: list[str],
        recommended_action: str,
        gao_references: list[str],
        explanation: str,
        signal_detail: list[dict],
    ) -> FraudAssessmentLog:
        fa = FraudAssessmentLog(
            tenant_id=tenant_id,
            transaction_id=transaction_id,
            composite_score=Decimal(str(round(composite_score, 2))),
            risk_tier=risk_tier,
            triggered_rules=triggered_rules,
            recommended_action=recommended_action,
            gao_references=gao_references,
            explanation=explanation,
            signal_detail=signal_detail,
        )
        self.db.add(fa)
        await self.db.flush()
        return fa

    async def create_anomaly_alert(
        self,
        tenant_id: UUID,
        grant_id: UUID,
        anomaly_type: str,
        severity: str,
        score: float,
        threshold: float,
        observed_value: Optional[float],
        description: str,
        gao_reference: Optional[str],
        auto_action: Optional[str],
    ) -> AnomalyAlert:
        aa = AnomalyAlert(
            tenant_id=tenant_id,
            grant_id=grant_id,
            anomaly_type=anomaly_type,
            severity=severity,
            score=Decimal(str(round(score, 2))),
            threshold=Decimal(str(round(threshold, 2))),
            observed_value=Decimal(str(round(observed_value, 2))) if observed_value is not None else None,
            description=description,
            gao_reference=gao_reference,
            auto_action=auto_action,
        )
        self.db.add(aa)
        await self.db.flush()
        return aa

    async def get_fraud_assessment(self, transaction_id: UUID) -> Optional[FraudAssessmentLog]:
        result = await self.db.execute(
            select(FraudAssessmentLog)
            .where(FraudAssessmentLog.transaction_id == transaction_id)
            .order_by(FraudAssessmentLog.created_at.desc())
            .limit(1)
        )
        return result.scalar_one_or_none()

    async def check_duplicate_invoice(
        self, tenant_id: UUID, vendor_id: UUID, invoice_ref: str, amount: Decimal
    ) -> list[Transaction]:
        result = await self.db.execute(
            select(Transaction).where(
                and_(
                    Transaction.tenant_id == tenant_id,
                    Transaction.vendor_id == vendor_id,
                    Transaction.invoice_ref == invoice_ref,
                    Transaction.amount == amount,
                    Transaction.flag_status != "rejected",
                )
            ).limit(5)
        )
        return result.scalars().all()
