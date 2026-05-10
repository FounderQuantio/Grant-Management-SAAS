"""GovGuard™ — Celery Application Factory"""
from celery import Celery
from celery.schedules import crontab
from core.config import settings

celery_app = Celery(
    "govguard",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
    include=[
        "workers.payment_tasks",
        "workers.compliance_tasks",
        "workers.audit_tasks",
        "workers.sync_tasks",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_acks_late=True,
    worker_prefetch_multiplier=1,
    task_routes={
        "workers.payment_tasks.*": {"queue": "payments"},
        "workers.compliance_tasks.*": {"queue": "compliance"},
        "workers.audit_tasks.*": {"queue": "audit"},
        "workers.sync_tasks.*": {"queue": "sync"},
    },
    beat_schedule={
        "batch-duplicate-scan": {
            "task": "workers.payment_tasks.batch_duplicate_scan",
            "schedule": crontab(minute=0, hour="*/6"),
        },
        "refresh-compliance-scores": {
            "task": "workers.compliance_tasks.refresh_compliance_scores",
            "schedule": crontab(minute=0, hour=2),
        },
        "send-cap-reminders": {
            "task": "workers.audit_tasks.send_cap_reminders",
            "schedule": crontab(minute=0, hour=8),
        },
        "sam-gov-refresh": {
            "task": "workers.sync_tasks.sam_gov_refresh",
            "schedule": crontab(minute=0, hour=1, day_of_week=0),
        },
        "nightly-ml-retrain": {
            "task": "workers.payment_tasks.nightly_ml_retrain",
            "schedule": crontab(minute=0, hour=3),
        },
    },
)
