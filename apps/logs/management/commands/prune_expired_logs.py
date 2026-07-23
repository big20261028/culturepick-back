from __future__ import annotations

from datetime import datetime, time, timedelta
from pathlib import Path

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.db import IntegrityError, transaction
from django.db.models import Count, F
from django.db.models.functions import TruncDate
from django.utils import timezone

from apps.logs.models import (
    QnALog,
    QnALogDailyAggregate,
    SearchLog,
    SearchLogDailyAggregate,
    ViewLog,
    ViewLogDailyAggregate,
)


DEFAULT_RETENTION_DAYS = 90
DEFAULT_BATCH_SIZE = 1_000
MAX_BATCH_SIZE = 10_000
LOG_POLICIES = (
    (
        SearchLog,
        SearchLogDailyAggregate,
        ("filter_region", "filter_genre", "filter_status"),
    ),
    (
        ViewLog,
        ViewLogDailyAggregate,
        ("performance_id", "log_type"),
    ),
    (QnALog, QnALogDailyAggregate, ()),
)


class Command(BaseCommand):
    help = (
        "Report or delete expired search/view/Q&A rows and raw Codex conversation "
        "JSONL files. Dry-run is the default."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--retention-days",
            type=int,
            default=None,
            help=(
                "Delete data older than this many days "
                f"(default: LOG_RAW_RETENTION_DAYS or {DEFAULT_RETENTION_DAYS})."
            ),
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=None,
            help=(
                "Maximum database rows deleted per transaction "
                f"(default: LOG_RETENTION_BATCH_SIZE or {DEFAULT_BATCH_SIZE})."
            ),
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Actually delete expired data. Without this flag the command only reports counts.",
        )

    def handle(self, *args, **options):
        retention_days = options["retention_days"]
        if retention_days is None:
            retention_days = getattr(
                settings,
                "LOG_RAW_RETENTION_DAYS",
                DEFAULT_RETENTION_DAYS,
            )
        batch_size = options["batch_size"]
        if batch_size is None:
            batch_size = getattr(
                settings,
                "LOG_RETENTION_BATCH_SIZE",
                DEFAULT_BATCH_SIZE,
            )
        apply_changes = options["apply"]
        if retention_days < 1:
            raise CommandError("--retention-days must be at least 1.")
        if not 1 <= batch_size <= MAX_BATCH_SIZE:
            raise CommandError(f"--batch-size must be between 1 and {MAX_BATCH_SIZE}.")

        now = timezone.now()
        current_timezone = timezone.get_current_timezone()
        cutoff_date = timezone.localdate(now, current_timezone) - timedelta(
            days=retention_days
        )
        cutoff = timezone.make_aware(
            datetime.combine(cutoff_date, time.min),
            current_timezone,
        )
        mode = "APPLY" if apply_changes else "DRY-RUN"
        self.stdout.write(
            f"{mode}: retention={retention_days} days, "
            f"cutoff_day={cutoff_date.isoformat()} ({current_timezone})"
        )

        total_rows = 0
        aggregate_buckets = 0
        for model, aggregate_model, group_fields in LOG_POLICIES:
            queryset = model.objects.filter(created_at__lt=cutoff)
            count = queryset.count()
            total_rows += count
            self.stdout.write(f"{model.__name__}: {count} expired row(s)")
            if apply_changes and count:
                deleted, buckets = self._aggregate_then_delete_in_batches(
                    queryset=queryset,
                    aggregate_model=aggregate_model,
                    group_fields=group_fields,
                    current_timezone=current_timezone,
                    batch_size=batch_size,
                )
                if deleted != count:
                    self.stderr.write(
                        self.style.WARNING(
                            f"{model.__name__}: expected {count} rows but deleted "
                            f"{deleted}; concurrent writes may have occurred."
                        )
                    )
                aggregate_buckets += buckets

        conversation_files = list(self._expired_conversation_files(cutoff))
        self.stdout.write(
            f"Conversation JSONL: {len(conversation_files)} expired file(s)"
        )
        if apply_changes:
            for path in conversation_files:
                self._unlink_safe_conversation_file(path)

        action = "deleted" if apply_changes else "would delete"
        self.stdout.write(
            self.style.SUCCESS(
                f"{mode}: {action} {total_rows} database row(s) and "
                f"{len(conversation_files)} conversation file(s); "
                f"{aggregate_buckets} aggregate bucket(s) updated."
            )
        )

    def _aggregate_then_delete_in_batches(
        self,
        *,
        queryset,
        aggregate_model,
        group_fields,
        current_timezone,
        batch_size,
    ):
        deleted_rows = 0
        updated_buckets = 0
        model = queryset.model

        while True:
            with transaction.atomic():
                ids = list(
                    queryset.select_for_update()
                    .order_by("pk")
                    .values_list("pk", flat=True)[:batch_size]
                )
                if not ids:
                    break

                batch_queryset = model.objects.filter(pk__in=ids)
                aggregate_fields = ("aggregate_date", *group_fields)
                groups = (
                    batch_queryset.annotate(
                        aggregate_date=TruncDate(
                            "created_at",
                            tzinfo=current_timezone,
                        )
                    )
                    .values(*aggregate_fields)
                    .annotate(aggregate_count=Count("pk"))
                )

                for group in groups:
                    count = group.pop("aggregate_count")
                    log_date = group.pop("aggregate_date")
                    self._increment_aggregate(
                        aggregate_model,
                        {"log_date": log_date, **group},
                        count,
                    )
                    updated_buckets += 1

                deleted_rows += batch_queryset.delete()[0]
        return deleted_rows, updated_buckets

    @staticmethod
    def _increment_aggregate(aggregate_model, lookup, count):
        now = timezone.now()
        updated = aggregate_model.objects.filter(**lookup).update(
            count=F("count") + count,
            updated_at=now,
        )
        if updated:
            return
        try:
            aggregate_model.objects.create(**lookup, count=count)
        except IntegrityError:
            aggregate_model.objects.filter(**lookup).update(
                count=F("count") + count,
                updated_at=now,
            )

    @staticmethod
    def _conversation_directory() -> Path:
        return Path(settings.BASE_DIR).resolve() / ".codex" / "conversations"

    def _expired_conversation_files(self, cutoff):
        directory = self._conversation_directory()
        if not directory.is_dir() or directory.is_symlink():
            return

        cutoff_timestamp = cutoff.timestamp()
        for path in directory.iterdir():
            if (
                path.suffix.lower() != ".jsonl"
                or path.is_symlink()
                or not path.is_file()
            ):
                continue
            try:
                if path.stat().st_mtime < cutoff_timestamp:
                    yield path
            except OSError:
                self.stderr.write(
                    self.style.WARNING("Skipped an unreadable conversation log file.")
                )

    def _unlink_safe_conversation_file(self, path: Path):
        directory = self._conversation_directory()
        try:
            resolved = path.resolve(strict=True)
        except OSError:
            self.stderr.write(
                self.style.WARNING("Skipped a conversation log that no longer exists.")
            )
            return

        if (
            path.is_symlink()
            or resolved.parent != directory
            or resolved.suffix.lower() != ".jsonl"
        ):
            self.stderr.write(
                self.style.WARNING("Skipped a conversation path outside the managed directory.")
            )
            return
        try:
            resolved.unlink()
        except OSError:
            self.stderr.write(
                self.style.WARNING("Failed to delete an expired conversation log file.")
            )
