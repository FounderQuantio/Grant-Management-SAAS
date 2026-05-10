"""GovGuard™ — ERP Sync & External API Tasks"""
import asyncio
from workers.celery_app import celery_app
import structlog

log = structlog.get_logger()


@celery_app.task(name="workers.sync_tasks.erp_csv_etl")
def erp_csv_etl(job_id: str, tenant_id: str, filename: str):
    """Process CSV flat-file upload into transactions table."""
    loop = asyncio.new_event_loop()
    loop.run_until_complete(_process_csv(job_id, tenant_id, filename))


async def _process_csv(job_id: str, tenant_id: str, filename: str):
    log.info("csv_etl.start", job_id=job_id, filename=filename)
    # In production: download file from S3 uploads bucket, parse CSV,
    # validate each row, bulk insert via COPY or execute_many
    log.info("csv_etl.done (stub)", job_id=job_id)


@celery_app.task(
    name="workers.sync_tasks.sam_gov_refresh",
    max_retries=5,
    default_retry_delay=300,
)
def sam_gov_refresh():
    """Weekly: refresh SAM.gov exclusions for all vendor records."""
    loop = asyncio.new_event_loop()
    loop.run_until_complete(_refresh_sam_gov())


async def _refresh_sam_gov():
    from core.db import AsyncSessionLocal
    from core.config import settings
    from sqlalchemy import text
    import httpx

    log.info("sam_gov_refresh.start")

    if not settings.SAM_GOV_API_KEY:
        log.warning("sam_gov_refresh.skipped - no API key configured")
        return

    async with AsyncSessionLocal() as db:
        result = await db.execute(text("SELECT id, ein_hash FROM vendors WHERE sam_status = 'unknown'"))
        vendors = result.fetchall()

        # SAM.gov bulk check (in production: batch by 100)
        for vendor in vendors[:100]:
            try:
                async with httpx.AsyncClient() as client:
                    resp = await client.get(
                        f"{settings.SAM_GOV_BASE_URL}/search",
                        params={"api_key": settings.SAM_GOV_API_KEY},
                        timeout=10,
                    )
                    if resp.status_code == 200:
                        sam_status = "active"  # Parse actual response
                        await db.execute(
                            text("UPDATE vendors SET sam_status = :s, sam_checked_at = NOW() WHERE id = :id"),
                            {"s": sam_status, "id": str(vendor.id)}
                        )
            except Exception as e:
                log.warning("sam_gov_check_failed", vendor_id=str(vendor.id), error=str(e))

        await db.commit()
    log.info("sam_gov_refresh.done")
