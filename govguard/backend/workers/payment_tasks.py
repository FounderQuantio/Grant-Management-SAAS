"""GovGuard™ — Payment & ML Celery Tasks"""
import asyncio
import time
from decimal import Decimal
from uuid import UUID

import structlog
from celery import Task

from workers.celery_app import celery_app

log = structlog.get_logger()


class DatabaseTask(Task):
    """Base task that provides an async DB session."""
    _loop = None

    def get_loop(self):
        if self._loop is None or self._loop.is_closed():
            self._loop = asyncio.new_event_loop()
            asyncio.set_event_loop(self._loop)
        return self._loop


@celery_app.task(
    bind=True,
    base=DatabaseTask,
    name="workers.payment_tasks.score_transaction_async",
    max_retries=3,
    default_retry_delay=5,
)
def score_transaction_async(self, tx_id: str, tenant_id: str):
    """Score a single transaction using ML model. Target: 200ms."""
    loop = self.get_loop()
    loop.run_until_complete(_score_transaction(self, tx_id, tenant_id))


async def _score_transaction(task, tx_id: str, tenant_id: str):
    start = time.monotonic()
    try:
        from core.db import AsyncSessionLocal
        from core.models import Transaction, RiskScoreLog
        from ml.risk_scorer import RiskScorer
        from sqlalchemy import select, and_, update
        import uuid

        scorer = RiskScorer()

        async with AsyncSessionLocal() as db:
            await db.execute(
                __import__('sqlalchemy').text("SET LOCAL app.current_tenant = :tid"),
                {"tid": tenant_id}
            )
            result = await db.execute(
                select(Transaction).where(
                    and_(Transaction.id == uuid.UUID(tx_id), Transaction.tenant_id == uuid.UUID(tenant_id))
                )
            )
            tx = result.scalar_one_or_none()
            if not tx:
                return

            features = {
                "amount": float(tx.amount),
                "invoice_ref_len": len(tx.invoice_ref),
                "is_round_number": float(tx.amount) % 100 == 0,
            }
            score, weights = scorer.predict(features)
            elapsed_ms = int((time.monotonic() - start) * 1000)

            flag_status = "pending"
            flag_reason = None
            if score >= 75.0:
                flag_status = "flagged"
                flag_reason = f"High risk score: {score:.1f}/100"

            await db.execute(
                update(Transaction)
                .where(Transaction.id == uuid.UUID(tx_id))
                .values(risk_score=Decimal(str(score)), flag_status=flag_status, flag_reason=flag_reason)
            )

            log_entry = RiskScoreLog(
                transaction_id=uuid.UUID(tx_id),
                tenant_id=uuid.UUID(tenant_id),
                model_version="isolation_forest_v1.0",
                score=Decimal(str(score)),
                feature_weights_json=weights,
                inference_ms=elapsed_ms,
            )
            db.add(log_entry)
            await db.commit()

            from core.cache import cache_set
            await cache_set(f"rs:{tx_id}", {
                "score": score,
                "feature_weights": weights,
                "model_version": "isolation_forest_v1.0",
                "explanation": f"Score: {score:.1f}/100",
                "is_high_risk": score >= 75.0,
            }, ttl=86400)

        log.info("transaction_scored", tx_id=tx_id, score=score, elapsed_ms=elapsed_ms)

    except Exception as exc:
        log.error("score_transaction_failed", tx_id=tx_id, error=str(exc))
        raise task.retry(exc=exc, countdown=2 ** task.request.retries * 5)


@celery_app.task(name="workers.payment_tasks.batch_duplicate_scan")
def batch_duplicate_scan():
    """Scan for duplicate invoices across all tenants. Runs every 6 hours."""
    loop = asyncio.new_event_loop()
    loop.run_until_complete(_batch_dup_scan())


async def _batch_dup_scan():
    log.info("batch_duplicate_scan.start")
    from core.db import AsyncSessionLocal
    from sqlalchemy import text

    async with AsyncSessionLocal() as db:
        result = await db.execute(
            text("""
                SELECT tenant_id, vendor_id, invoice_ref, amount, COUNT(*) as cnt
                FROM transactions
                WHERE flag_status = 'pending'
                  AND created_at > NOW() - INTERVAL '7 days'
                GROUP BY tenant_id, vendor_id, invoice_ref, amount
                HAVING COUNT(*) > 1
            """)
        )
        dupes = result.fetchall()
        for row in dupes:
            await db.execute(
                text("""
                    UPDATE transactions
                    SET flag_status = 'suppressed',
                        flag_reason = 'Duplicate invoice detected in batch scan'
                    WHERE tenant_id = :tid
                      AND vendor_id = :vid
                      AND invoice_ref = :ref
                      AND amount = :amt
                      AND flag_status = 'pending'
                """),
                {"tid": str(row.tenant_id), "vid": str(row.vendor_id), "ref": row.invoice_ref, "amt": row.amount}
            )
        await db.commit()
    log.info("batch_duplicate_scan.done", duplicates_found=len(dupes))


@celery_app.task(name="workers.payment_tasks.nightly_ml_retrain")
def nightly_ml_retrain():
    """Champion/challenger ML model retraining. Max 4 hours."""
    log.info("nightly_ml_retrain.start")
    # In production: load training data from S3, train new model,
    # evaluate against holdout set, promote if accuracy improves
    log.info("nightly_ml_retrain.done (stub - implement with real training data)")
