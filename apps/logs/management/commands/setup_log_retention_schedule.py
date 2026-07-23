from __future__ import annotations

import json

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django_celery_beat.models import CrontabSchedule, PeriodicTask


TASK_NAME = "daily-prune-expired-logs"
TASK_PATH = "logs.prune_expired_logs"
DEFAULT_HOUR = 3
DEFAULT_MINUTE = 30


class Command(BaseCommand):
    help = (
        "Create or update the daily Celery Beat schedule that aggregates and "
        "prunes expired raw logs."
    )

    def add_arguments(self, parser):
        parser.add_argument("--hour", type=int, default=DEFAULT_HOUR)
        parser.add_argument("--minute", type=int, default=DEFAULT_MINUTE)

    def handle(self, *args, **options):
        hour = options["hour"]
        minute = options["minute"]
        retention_days = settings.LOG_RAW_RETENTION_DAYS
        batch_size = settings.LOG_RETENTION_BATCH_SIZE

        if not 0 <= hour <= 23:
            raise CommandError("--hour must be between 0 and 23.")
        if not 0 <= minute <= 59:
            raise CommandError("--minute must be between 0 and 59.")
        if retention_days < 1:
            raise CommandError("LOG_RAW_RETENTION_DAYS must be at least 1.")
        if not 1 <= batch_size <= 10_000:
            raise CommandError(
                "LOG_RETENTION_BATCH_SIZE must be between 1 and 10000."
            )

        schedule, _ = CrontabSchedule.objects.get_or_create(
            minute=str(minute),
            hour=str(hour),
            day_of_week="*",
            day_of_month="*",
            month_of_year="*",
            timezone=settings.TIME_ZONE,
        )
        periodic_task, created = PeriodicTask.objects.update_or_create(
            name=TASK_NAME,
            defaults={
                "task": TASK_PATH,
                "crontab": schedule,
                "interval": None,
                "solar": None,
                "clocked": None,
                "args": json.dumps([]),
                "kwargs": json.dumps(
                    {
                        "retention_days": retention_days,
                        "batch_size": batch_size,
                    }
                ),
                "enabled": True,
            },
        )
        action = "created" if created else "updated"
        self.stdout.write(
            self.style.SUCCESS(
                f"{action}: {periodic_task.name} -> {periodic_task.task} "
                f"at {hour:02d}:{minute:02d} {settings.TIME_ZONE}; "
                f"retention={retention_days} days, batch={batch_size}"
            )
        )

