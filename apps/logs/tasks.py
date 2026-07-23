from __future__ import annotations

from io import StringIO

from celery import shared_task
from django.conf import settings
from django.core.cache import cache
from django.core.management import call_command


RETENTION_TASK_LOCK_KEY = "logs:retention:daily-lock"
RETENTION_TASK_LOCK_SECONDS = 60 * 60


@shared_task(name="logs.prune_expired_logs")
def prune_expired_logs_task(retention_days=None, batch_size=None):
    """Run the idempotent raw-log retention policy once.

    The shared cache lock prevents overlapping Celery executions. Each database
    day is aggregated and deleted in one transaction, so retries cannot delete
    raw rows without first preserving their non-identifying counts.
    """

    retention_days = (
        settings.LOG_RAW_RETENTION_DAYS
        if retention_days is None
        else retention_days
    )
    batch_size = (
        settings.LOG_RETENTION_BATCH_SIZE
        if batch_size is None
        else batch_size
    )

    acquired = cache.add(
        RETENTION_TASK_LOCK_KEY,
        "running",
        timeout=RETENTION_TASK_LOCK_SECONDS,
    )
    if not acquired:
        return {"status": "skipped", "reason": "already_running"}

    output = StringIO()
    try:
        call_command(
            "prune_expired_logs",
            "--apply",
            "--retention-days",
            str(retention_days),
            "--batch-size",
            str(batch_size),
            stdout=output,
        )
        return {"status": "ok"}
    finally:
        cache.delete(RETENTION_TASK_LOCK_KEY)
