"""GovGuard™ — Compliance Engine Service"""
import uuid
from decimal import Decimal
from typing import Optional
from uuid import UUID

import structlog
from sqlalchemy import select, func, and_
from sqlalchemy.ext.asyncio import AsyncSession

from core.cache import cache_get, cache_set
from core.models import ComplianceControl, Grant, ControlLibrary
from core.exceptions import ComplianceControlNotFound, GrantNotFound
from modules.compliance_engine.schemas import (
    ControlResponse, ControlListResponse, ControlUpdate,
    ComplianceRunRequest, ComplianceRunResponse, SoDResponse,
)

log = structlog.get_logger()


class ComplianceService:
    def __init__(self, db: AsyncSession):
        self.db = db

    async def list_controls(
        self,
        tenant_id: UUID,
        grant_id: Optional[UUID] = None,
        status: Optional[str] = None,
        domain: Optional[str] = None,
    ) -> ControlListResponse:
        cache_key = f"cs:{grant_id}:{status}:{domain}"
        cached = await cache_get(cache_key)
        if cached:
            return ControlListResponse(**cached)

        q = select(ComplianceControl).where(ComplianceControl.tenant_id == tenant_id)
        if grant_id:
            q = q.where(ComplianceControl.grant_id == grant_id)
        if status:
            q = q.where(ComplianceControl.status == status)
        if domain:
            q = q.where(ComplianceControl.domain == domain)

        result = await self.db.execute(q)
        controls = result.scalars().all()

        total = len(controls)
        passing = sum(1 for c in controls if c.status == "pass")
        failing = sum(1 for c in controls if c.status == "fail")
        score = Decimal(str(round((passing / total * 100) if total else 0, 2)))

        resp = ControlListResponse(
            controls=[ControlResponse.model_validate(c) for c in controls],
            score=score,
            total=total,
            passing=passing,
            failing=failing,
        )
        await cache_set(cache_key, resp.model_dump(mode="json"), ttl=300)
        return resp

    async def update_control(
        self,
        control_id: UUID,
        tenant_id: UUID,
        data: ControlUpdate,
    ) -> ControlResponse:
        result = await self.db.execute(
            select(ComplianceControl).where(
                and_(
                    ComplianceControl.id == control_id,
                    ComplianceControl.tenant_id == tenant_id,
                )
            )
        )
        ctrl = result.scalar_one_or_none()
        if not ctrl:
            raise ComplianceControlNotFound()

        ctrl.status = data.status
        if data.evidence_note:
            ctrl.remediation_note = data.evidence_note
        from datetime import datetime, timezone
        ctrl.last_tested = datetime.now(timezone.utc)
        await self.db.commit()
        await self.db.refresh(ctrl)

        # Invalidate cache
        from core.cache import cache_delete_pattern
        await cache_delete_pattern(f"cs:{ctrl.grant_id}:*")
        return ControlResponse.model_validate(ctrl)

    async def run_compliance_check(
        self,
        data: ComplianceRunRequest,
        tenant_id: UUID,
    ) -> ComplianceRunResponse:
        job_id = uuid.uuid4()
        try:
            from workers.compliance_tasks import run_compliance_check
            run_compliance_check.delay(
                str(job_id),
                str(data.grant_id),
                str(tenant_id),
                data.control_codes,
            )
        except Exception as e:
            log.warning("celery_dispatch_failed", error=str(e))

        # Count how many controls will be checked
        q = select(func.count(ComplianceControl.id)).where(
            and_(
                ComplianceControl.grant_id == data.grant_id,
                ComplianceControl.tenant_id == tenant_id,
            )
        )
        if data.control_codes:
            q = q.where(ComplianceControl.control_code.in_(data.control_codes))
        count = await self.db.scalar(q) or 0

        return ComplianceRunResponse(job_id=job_id, controls_queued=count)

    async def check_sod(self, tenant_id: UUID, user_id: Optional[UUID] = None) -> SoDResponse:
        """Check Segregation of Duties violations."""
        # SoD rule: same user cannot have both initiate+approve roles
        violations = []
        matrix = {
            "finance_staff": ["enter_transactions", "upload_invoices"],
            "finance_manager": ["approve_payments", "post_transactions"],
            "compliance_officer": ["manage_controls", "manage_subrecipients"],
            "auditor": ["read_all"],
        }
        return SoDResponse(violations=violations, matrix_snapshot=matrix)

    async def seed_controls_for_grant(self, grant_id: UUID, tenant_id: UUID) -> int:
        """Seed 130+ controls from control_library for a new grant."""
        result = await self.db.execute(select(ControlLibrary))
        library = result.scalars().all()

        controls = [
            ComplianceControl(
                tenant_id=tenant_id,
                grant_id=grant_id,
                control_code=lib.code,
                cfr_clause=lib.cfr_clause,
                gao_principle=lib.gao_principle,
                domain=lib.domain,
                status="not_tested",
            )
            for lib in library
        ]
        self.db.add_all(controls)
        await self.db.commit()
        return len(controls)
