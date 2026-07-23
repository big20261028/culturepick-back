from __future__ import annotations

from datetime import timedelta
from io import StringIO
import os
from pathlib import Path
from tempfile import TemporaryDirectory

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone
from django_celery_beat.models import PeriodicTask

from apps.logs.models import (
    QnALog,
    QnALogDailyAggregate,
    SearchLog,
    SearchLogDailyAggregate,
    ViewLog,
    ViewLogDailyAggregate,
)


class PruneExpiredLogsCommandTests(TestCase):
    def setUp(self):
        self.now = timezone.now()
        self.old_created_at = self.now - timedelta(days=91)

        for model, values in (
            (SearchLog, {"keyword": "old"}),
            (ViewLog, {"performance_id": "PF-OLD"}),
            (QnALog, {"question": "old question", "answer": "old answer"}),
        ):
            old_row = model.objects.create(**values)
            model.objects.filter(pk=old_row.pk).update(
                created_at=self.old_created_at
            )
            model.objects.create(
                **{
                    key: value.replace("old", "recent").replace("OLD", "RECENT")
                    for key, value in values.items()
                }
            )

    def test_dry_run_is_default_and_preserves_database_and_summary(self):
        with TemporaryDirectory() as temporary:
            base_dir = Path(temporary)
            conversations = base_dir / ".codex" / "conversations"
            conversations.mkdir(parents=True)
            old_log = conversations / "old-session.jsonl"
            old_log.write_text('{"role":"user"}\n', encoding="utf-8")
            old_timestamp = self.old_created_at.timestamp()
            os.utime(old_log, (old_timestamp, old_timestamp))
            summary = base_dir / ".codex" / "conversation-log.md"
            summary.write_text("# durable summary\n", encoding="utf-8")

            stdout = StringIO()
            with override_settings(BASE_DIR=base_dir):
                call_command(
                    "prune_expired_logs",
                    "--batch-size",
                    "1",
                    stdout=stdout,
                )

            self.assertEqual(SearchLog.objects.count(), 2)
            self.assertEqual(ViewLog.objects.count(), 2)
            self.assertEqual(QnALog.objects.count(), 2)
            self.assertTrue(old_log.exists())
            self.assertEqual(summary.read_text(encoding="utf-8"), "# durable summary\n")
            self.assertIn("DRY-RUN", stdout.getvalue())

    def test_apply_deletes_only_expired_rows_and_jsonl_files(self):
        with TemporaryDirectory() as temporary:
            base_dir = Path(temporary)
            conversations = base_dir / ".codex" / "conversations"
            conversations.mkdir(parents=True)
            old_log = conversations / "old-session.jsonl"
            recent_log = conversations / "recent-session.jsonl"
            ignored_file = conversations / "notes.txt"
            for path in (old_log, recent_log, ignored_file):
                path.write_text("content\n", encoding="utf-8")
            old_timestamp = self.old_created_at.timestamp()
            os.utime(old_log, (old_timestamp, old_timestamp))
            os.utime(ignored_file, (old_timestamp, old_timestamp))

            with override_settings(BASE_DIR=base_dir):
                call_command(
                    "prune_expired_logs",
                    "--apply",
                    "--batch-size",
                    "1",
                    stdout=StringIO(),
                )

            self.assertEqual(list(SearchLog.objects.values_list("keyword", flat=True)), ["recent"])
            self.assertEqual(
                list(ViewLog.objects.values_list("performance_id", flat=True)),
                ["PF-RECENT"],
            )
            self.assertEqual(
                list(QnALog.objects.values_list("question", flat=True)),
                ["recent question"],
            )
            self.assertFalse(old_log.exists())
            self.assertTrue(recent_log.exists())
            self.assertTrue(ignored_file.exists())
            self.assertEqual(
                SearchLogDailyAggregate.objects.get().count,
                1,
            )
            self.assertEqual(
                ViewLogDailyAggregate.objects.get().count,
                1,
            )
            self.assertEqual(
                QnALogDailyAggregate.objects.get().count,
                1,
            )
            search_bucket = SearchLogDailyAggregate.objects.values().get()
            self.assertNotIn("keyword", search_bucket)
            self.assertNotIn("user_id", search_bucket)
            qna_bucket = QnALogDailyAggregate.objects.values().get()
            self.assertNotIn("question", qna_bucket)
            self.assertNotIn("answer", qna_bucket)
            self.assertNotIn("user_id", qna_bucket)

    def test_late_raw_row_increments_existing_daily_bucket_idempotently(self):
        with TemporaryDirectory() as temporary:
            base_dir = Path(temporary)
            with override_settings(BASE_DIR=base_dir):
                call_command(
                    "prune_expired_logs",
                    "--apply",
                    stdout=StringIO(),
                )
                late_row = SearchLog.objects.create(keyword="never aggregate me")
                SearchLog.objects.filter(pk=late_row.pk).update(
                    created_at=self.old_created_at
                )
                call_command(
                    "prune_expired_logs",
                    "--apply",
                    stdout=StringIO(),
                )

            self.assertEqual(SearchLogDailyAggregate.objects.get().count, 2)
            self.assertFalse(SearchLog.objects.filter(keyword="never aggregate me").exists())

    def test_rejects_unsafe_retention_and_batch_values(self):
        with self.assertRaises(CommandError):
            call_command("prune_expired_logs", "--retention-days", "0")
        with self.assertRaises(CommandError):
            call_command("prune_expired_logs", "--batch-size", "10001")


class LogRetentionScheduleCommandTests(TestCase):
    @override_settings(
        LOG_RAW_RETENTION_DAYS=90,
        LOG_RETENTION_BATCH_SIZE=750,
        TIME_ZONE="Asia/Seoul",
    )
    def test_schedule_setup_is_idempotent_and_records_policy_arguments(self):
        call_command(
            "setup_log_retention_schedule",
            "--hour",
            "3",
            "--minute",
            "30",
            stdout=StringIO(),
        )
        call_command(
            "setup_log_retention_schedule",
            "--hour",
            "3",
            "--minute",
            "30",
            stdout=StringIO(),
        )

        tasks = PeriodicTask.objects.filter(name="daily-prune-expired-logs")
        self.assertEqual(tasks.count(), 1)
        task = tasks.get()
        self.assertEqual(task.task, "logs.prune_expired_logs")
        self.assertEqual(task.crontab.hour, "3")
        self.assertEqual(task.crontab.minute, "30")
        self.assertEqual(
            task.kwargs,
            '{"retention_days": 90, "batch_size": 750}',
        )
