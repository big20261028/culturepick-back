from __future__ import annotations

import hashlib
from io import StringIO
import json
from pathlib import Path
from tempfile import TemporaryDirectory

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.recommendations.models import (
    RecommendationSession,
    TrainingExampleCandidate,
)

User = get_user_model()


class TrainingExportCommandTests(TestCase):
    def setUp(self):
        self.reviewer = User.objects.create_user(
            email="training-reviewer@example.com",
            password="ValidPass123!",
            is_staff=True,
        )

    def _candidate(
        self,
        *,
        status=TrainingExampleCandidate.Status.AUTO_APPROVED,
        approved=True,
        reviewed=True,
        request_text="공연 추천",
    ):
        session = RecommendationSession.objects.create(
            request_text=request_text,
            provider="openai",
            validation_status=RecommendationSession.ValidationStatus.PASSED,
        )
        return TrainingExampleCandidate.objects.create(
            source_session=session,
            status=status,
            approved_for_training=approved,
            reviewed_by=self.reviewer if reviewed else None,
            reviewed_at=timezone.now() if reviewed else None,
            quality_score=8,
            input_payload={
                "task": "recommendation_reasoning",
                "user_request": request_text,
                "candidates": [{"performance_id": "PF-SAFE"}],
            },
            output_payload={"summary": "안전한 추천입니다."},
            chosen_output={"summary": "검수된 추천입니다."},
        )

    def test_dry_run_is_default_and_does_not_write_or_update(self):
        candidate = self._candidate()
        stdout = StringIO()

        call_command(
            "export_recommendation_training_data",
            "--dataset-version",
            "dry-run-v1",
            stdout=stdout,
        )

        candidate.refresh_from_db()
        self.assertEqual(
            candidate.status,
            TrainingExampleCandidate.Status.AUTO_APPROVED,
        )
        self.assertIsNone(candidate.exported_at)
        self.assertIn("DRY-RUN: 1 approved candidate", stdout.getvalue())

    def test_apply_exports_only_approved_and_deidentifies_records(self):
        candidate = self._candidate(
            request_text=(
                "test@example.com 010-1234-5678에게 알려줘. "
                "OPENAI_API_KEY=sk-proj-abcdefghijklmnopqrstuvwxyz "
                "접속 IP는 192.168.0.10"
            )
        )
        candidate.input_payload.update(
            {
                "session_id": 123,
                "user_id": 456,
                "user_profile": {
                    "address": "서울시 어느 길 1",
                    "safe_preference": "뮤지컬",
                },
            }
        )
        candidate.save(update_fields=["input_payload"])
        self._candidate(
            status=TrainingExampleCandidate.Status.NEEDS_REVIEW,
            approved=False,
            request_text="검토 전 후보",
        )

        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            backend_root = root / "culturepick-back"
            output_repository = root / "culturepick-training-data"
            backend_root.mkdir()
            output_repository.mkdir()
            with override_settings(BASE_DIR=backend_root):
                call_command(
                    "export_recommendation_training_data",
                    "--output-dir",
                    str(output_repository),
                    "--dataset-version",
                    "approved-v1",
                    "--batch-size",
                    "1",
                    "--apply",
                    stdout=StringIO(),
                )

            version_dir = (
                output_repository
                / "datasets"
                / "recommendations"
                / "approved-v1"
            )
            data_path = version_dir / "data.jsonl"
            manifest_path = version_dir / "manifest.json"
            raw_data = data_path.read_text(encoding="utf-8")
            record = json.loads(raw_data)
            manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

            self.assertNotIn("test@example.com", raw_data)
            self.assertNotIn("010-1234-5678", raw_data)
            self.assertNotIn("abcdefghijklmnopqrstuvwxyz", raw_data)
            self.assertNotIn("192.168.0.10", raw_data)
            self.assertNotIn("서울시 어느 길 1", raw_data)
            self.assertNotIn("session_id", raw_data)
            self.assertNotIn("user_id", raw_data)
            self.assertIn("[REDACTED_EMAIL]", raw_data)
            self.assertIn("[REDACTED_PHONE]", raw_data)
            self.assertEqual(record["output"]["summary"], "검수된 추천입니다.")
            self.assertNotIn("source_session_id", record["metadata"])
            self.assertEqual(manifest["files"][0]["records"], 1)
            self.assertEqual(
                manifest["files"][0]["sha256"],
                hashlib.sha256(data_path.read_bytes()).hexdigest(),
            )

        candidate.refresh_from_db()
        self.assertEqual(
            candidate.status,
            TrainingExampleCandidate.Status.EXPORTED,
        )
        self.assertIsNotNone(candidate.exported_at)

    def test_apply_requires_existing_direct_sibling_output_directory(self):
        self._candidate()
        with TemporaryDirectory() as temporary:
            backend_root = Path(temporary) / "culturepick-back"
            unsafe_output = backend_root / "training-data"
            unsafe_output.mkdir(parents=True)
            with override_settings(BASE_DIR=backend_root):
                with self.assertRaises(CommandError):
                    call_command(
                        "export_recommendation_training_data",
                        "--output-dir",
                        str(unsafe_output),
                        "--dataset-version",
                        "unsafe-v1",
                        "--apply",
                        stdout=StringIO(),
                    )

    def test_apply_never_exports_boolean_approved_row_with_review_status(self):
        self._candidate(
            status=TrainingExampleCandidate.Status.NEEDS_REVIEW,
            approved=True,
        )
        with TemporaryDirectory() as temporary:
            root = Path(temporary)
            backend_root = root / "culturepick-back"
            output_repository = root / "culturepick-training-data"
            backend_root.mkdir()
            output_repository.mkdir()
            with override_settings(BASE_DIR=backend_root):
                with self.assertRaisesMessage(
                    CommandError,
                    "No approved training examples",
                ):
                    call_command(
                        "export_recommendation_training_data",
                        "--output-dir",
                        str(output_repository),
                        "--dataset-version",
                        "review-v1",
                        "--apply",
                        stdout=StringIO(),
                    )

    def test_auto_approved_candidate_without_human_review_is_not_exported(self):
        self._candidate(approved=True, reviewed=False)

        stdout = StringIO()
        call_command(
            "export_recommendation_training_data",
            "--dataset-version",
            "unreviewed-v1",
            stdout=stdout,
        )

        self.assertIn("DRY-RUN: 0 approved candidate", stdout.getvalue())
