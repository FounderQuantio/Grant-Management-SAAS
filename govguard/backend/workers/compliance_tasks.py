"""GovGuard™ — Compliance Celery Tasks"""
import asyncio
from uuid import UUID

import structlog
from workers.celery_app import celery_app

log = structlog.get_logger()


@celery_app.task(
    name="workers.compliance_tasks.run_compliance_check",
    bind=True,
    max_retries=2,
)
def run_compliance_check(self, job_id: str, grant_id: str, tenant_id: str, control_codes=None):
    """Run compliance checks for a grant against 2 CFR 200 rules."""
    loop = asyncio.new_event_loop()
    loop.run_until_complete(_run_compliance(job_id, grant_id, tenant_id, control_codes))


async def _run_compliance(job_id: str, grant_id: str, tenant_id: str, control_codes=None):
    from core.db import AsyncSessionLocal
    from core.models import ComplianceControl, Grant
    from sqlalchemy import select, and_
    from datetime import datetime, timezone
    import uuid

    log.info("compliance_check.start", grant_id=grant_id, job_id=job_id)

    async with AsyncSessionLocal() as db:
        await db.execute(
            __import__("sqlalchemy").text("SET LOCAL app.current_tenant = :tid"),
            {"tid": tenant_id}
        )

        # Load controls
        q = select(ComplianceControl).where(
            and_(
                ComplianceControl.grant_id == uuid.UUID(grant_id),
                ComplianceControl.tenant_id == uuid.UUID(tenant_id),
            )
        )
        if control_codes:
            q = q.where(ComplianceControl.control_code.in_(control_codes))

        result = await db.execute(q)
        controls = result.scalars().all()

        # Load grant for budget validation
        grant = await db.get(Grant, uuid.UUID(grant_id))

        passed = 0
        failed = 0

        for ctrl in controls:
            # Each domain has its own rule engine
            status = await _evaluate_control(ctrl, grant, db)
            ctrl.status = status
            ctrl.last_tested = datetime.now(timezone.utc)
            if status == "pass":
                passed += 1
            elif status == "fail":
                failed += 1

        # Update grant compliance_score
        total = len(controls)
        if total > 0 and grant:
            grant.compliance_score = round(passed / total * 100, 2)

        await db.commit()

    log.info("compliance_check.done", grant_id=grant_id, passed=passed, failed=failed)


async def _evaluate_control(ctrl, grant, db) -> str:
    """Evaluate a single control. Returns pass/fail/not_applicable."""
    from modules.compliance_engine.rules import evaluate_rule
    try:
        return await evaluate_rule(ctrl.control_code, ctrl.domain, grant, db)
    except Exception:
        return "not_tested"


@celery_app.task(name="workers.compliance_tasks.refresh_compliance_scores")
def refresh_compliance_scores():
    """Nightly: recalculate compliance scores for all active grants."""
    loop = asyncio.new_event_loop()
    loop.run_until_complete(_refresh_all_scores())


async def _refresh_all_scores():
    from core.db import AsyncSessionLocal
    from sqlalchemy import text

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text("SELECT DISTINCT tenant_id, id FROM grants WHERE status = 'active'")
        )
        grants = result.fetchall()
        for row in grants:
            try:
                run_compliance_check.delay("refresh", str(row.id), str(row.tenant_id))
            except Exception:
                pass
    log.info("refresh_compliance_scores.queued", count=len(grants))
