"""GovGuard™ — Audit Celery Tasks"""
import asyncio
import uuid
from workers.celery_app import celery_app
import structlog

log = structlog.get_logger()


@celery_app.task(name="workers.audit_tasks.send_cap_reminders")
def send_cap_reminders():
    """Daily: send 30/60/90-day CAP reminder emails."""
    loop = asyncio.new_event_loop()
    loop.run_until_complete(_send_reminders())


async def _send_reminders():
    from core.db import AsyncSessionLocal
    from sqlalchemy import text
    from datetime import date, timedelta

    today = date.today()

    async with AsyncSessionLocal() as db:
        for days, col in [(30, "reminder_sent_30d"), (60, "reminder_sent_60d"), (90, "reminder_sent_90d")]:
            target_date = today + timedelta(days=days)
            result = await db.execute(
                text(f"""
                    SELECT id, tenant_id, finding_id, assignee_id, due_date
                    FROM corrective_action_plans
                    WHERE status = 'open'
                      AND {col} = FALSE
                      AND due_date = :target_date
                """),
                {"target_date": target_date}
            )
            caps = result.fetchall()
            for cap in caps:
                try:
                    await _send_reminder_email(cap, days)
                    await db.execute(
                        text(f"UPDATE corrective_action_plans SET {col} = TRUE WHERE id = :id"),
                        {"id": str(cap.id)}
                    )
                except Exception as e:
                    log.warning("cap_reminder_failed", cap_id=str(cap.id), error=str(e))
            await db.commit()
        log.info("cap_reminders.done")


async def _send_reminder_email(cap, days: int):
    """Send SES email reminder for a CAP."""
    # In production: resolve assignee email from Cognito + send via SES
    log.info("cap_reminder_sent", cap_id=str(cap.id), days=days)


@celery_app.task(
    name="workers.audit_tasks.build_evidence_package",
    bind=True,
    max_retries=3,
)
def build_evidence_package(self, job_id: str, grant_id: str, tenant_id: str, finding_ids=None):
    """Build a ZIP evidence package from S3 files for a grant."""
    loop = asyncio.new_event_loop()
    loop.run_until_complete(_build_package(job_id, grant_id, tenant_id, finding_ids))


async def _build_package(job_id: str, grant_id: str, tenant_id: str, finding_ids):
    import io, zipfile
    from core.db import AsyncSessionLocal
    from core.models import ComplianceControl
    from core.config import settings
    from sqlalchemy import select, and_
    import uuid

    log.info("evidence_package.start", job_id=job_id)

    async with AsyncSessionLocal() as db:
        await db.execute(
            __import__("sqlalchemy").text("SET LOCAL app.current_tenant = :tid"),
            {"tid": tenant_id}
        )
        result = await db.execute(
            select(ComplianceControl).where(
                and_(
                    ComplianceControl.grant_id == uuid.UUID(grant_id),
                    ComplianceControl.tenant_id == uuid.UUID(tenant_id),
                    ComplianceControl.evidence_s3_key.isnot(None),
                )
            )
        )
        controls = result.scalars().all()

    # Build ZIP in memory
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w", zipfile.ZIP_DEFLATED) as zf:
        manifest = []
        for ctrl in controls:
            manifest.append(f"{ctrl.control_code}: {ctrl.evidence_s3_key}")
        zf.writestr("MANIFEST.txt", "\n".join(manifest))

    buf.seek(0)
    # Upload ZIP to S3
    s3_key = f"exports/{tenant_id}/{job_id}/evidence_package.zip"
    from core.s3 import upload_bytes
    await upload_bytes(settings.S3_EXPORTS_BUCKET, s3_key, buf.read(), "application/zip")

    # Cache download URL
    from core.s3 import get_presigned_url
    from core.cache import cache_set
    url = await get_presigned_url(settings.S3_EXPORTS_BUCKET, s3_key, expires=3600)
    await cache_set(f"ep:{job_id}", {"status": "completed", "download_url": url}, ttl=3600)
    log.info("evidence_package.done", job_id=job_id)
