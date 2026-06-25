from __future__ import annotations

import json

from django.conf import settings
from django.core.management.base import BaseCommand
from django_celery_beat.models import CrontabSchedule, PeriodicTask


SCHEDULES = [
    {
        "name": "daily-sync-ongoing-performances",
        "task": "apps.performances.tasks.sync_ongoing_performances",
        "hour": "4",
        "minute": "10",
    },
    {
        "name": "daily-sync-upcoming-performances",
        "task": "apps.performances.tasks.sync_upcoming_performances",
        "hour": "4",
        "minute": "30",
    },
]


class Command(BaseCommand):
    help = "Register production celery beat schedules for KOPIS synchronization."

    def handle(self, *args, **options):
        timezone = getattr(settings, "TIME_ZONE", "Asia/Seoul")

        for schedule in SCHEDULES:
            crontab, _ = CrontabSchedule.objects.get_or_create(
                minute=schedule["minute"],
                hour=schedule["hour"],
                day_of_week="*",
                day_of_month="*",
                month_of_year="*",
                timezone=timezone,
            )
            task, created = PeriodicTask.objects.update_or_create(
                name=schedule["name"],
                defaults={
                    "task": schedule["task"],
                    "crontab": crontab,
                    "interval": None,
                    "solar": None,
                    "clocked": None,
                    "args": json.dumps([]),
                    "kwargs": json.dumps({}),
                    "enabled": True,
                },
            )
            action = "created" if created else "updated"
            self.stdout.write(
                self.style.SUCCESS(
                    f"{action}: {task.name} -> {task.task} at {schedule['hour']}:{schedule['minute']} {timezone}"
                )
            )

        self.stdout.write(self.style.SUCCESS("Celery beat KOPIS schedules are ready."))
