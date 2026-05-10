"""GovGuard™ — Transaction Repository"""
import uuid
from datetime import date
from decimal import Decimal
from typing import Optional
from uuid import UUID

from sqlalchemy import select, update, func, and_
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.sql import text

from core.models import Transaction, Grant, RiskScoreLog
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
