from __future__ import annotations

import hashlib
import json
import os
from datetime import UTC
from pathlib import Path
import re
import shutil
import tempfile
from typing import Any

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.recommendations.models import TrainingExampleCandidate


DATASET_NAME = "culturepick-recommendation-training"
DATASET_SCHEMA_VERSION = "culturepick.recommendation-training.v1"
MANIFEST_SCHEMA_VERSION = "culturepick.training-manifest.v1"
DEIDENTIFICATION_POLICY_VERSION = "culturepick.deidentification.v1"
DEFAULT_BATCH_SIZE = 500
MAX_BATCH_SIZE = 5_000
MAX_RECORD_BYTES = 1024 * 1024

SAFE_VERSION_RE = re.compile(r"\A[A-Za-z0-9][A-Za-z0-9._-]{0,79}\Z")
SENSITIVE_FIELD_RE = re.compile(
    r"(?i)(?:"
    r"(?:^|_)(?:user_?id|session_?id|source_session_?id)(?:$|_)|"
    r"email|phone|mobile|nickname|username|full_?name|first_?name|last_?name|"
    r"address|postal|resident|registration|"
    r"password|passwd|secret|token|cookie|authorization|credential|api_?key"
    r")"
)
EMAIL_RE = re.compile(r"(?i)(?<![\w.+-])[\w.+-]+@[\w-]+(?:\.[\w-]+)+(?![\w.-])")
KOREAN_PHONE_RE = re.compile(
    r"(?<!\d)(?:(?:\+?82)[- .]?)?0?(?:1[016789]|2|[3-6][1-5])"
    r"[- .]?\d{3,4}[- .]?\d{4}(?!\d)"
)
RESIDENT_ID_RE = re.compile(r"(?<!\d)\d{6}[- ]?[1-4]\d{6}(?!\d)")
IP_ADDRESS_RE = re.compile(
    r"(?<!\d)(?:(?:25[0-5]|2[0-4]\d|1?\d?\d)\.){3}"
    r"(?:25[0-5]|2[0-4]\d|1?\d?\d)(?!\d)"
)
URL_CREDENTIAL_RE = re.compile(
    r"(?i)\b([a-z][a-z0-9+.-]*://)([^\s/:@]+):([^\s/@]+)@"
)
BEARER_RE = re.compile(r"(?i)\bBearer\s+[A-Za-z0-9._~+/=-]{8,}")
OPENAI_KEY_RE = re.compile(r"\bsk-(?:proj-)?[A-Za-z0-9_-]{16,}\b")
AWS_KEY_RE = re.compile(r"\b(?:AKIA|ASIA)[A-Z0-9]{16}\b")
JWT_RE = re.compile(
    r"\beyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\b"
)
SECRET_ASSIGNMENT_RE = re.compile(
    r"(?im)\b("
    r"(?:[A-Z][A-Z0-9_]*(?:API_KEY|SECRET|PASSWORD|TOKEN))|"
    r"OPENAI_API_KEY|AWS_ACCESS_KEY_ID|AWS_SECRET_ACCESS_KEY|AWS_SESSION_TOKEN|"
    r"DATABASE_URL|REDIS_URL|CELERY_BROKER_URL|AUTHORIZATION|COOKIE"
    r")\b(\s*(?:=|:)\s*)"
    r"(?:\"[^\"\r\n]*\"|'[^'\r\n]*'|[^\s,;\r\n]+)"
)
SECRET_QUERY_RE = re.compile(
    r"(?i)([?&](?:access_token|api_key|key|password|secret|signature|token)=)"
    r"[^&#\s]+"
)


class UnsafeTrainingRecord(ValueError):
    pass


def redact_sensitive_text(value: str) -> str:
    value = SECRET_ASSIGNMENT_RE.sub(
        lambda match: f"{match.group(1)}{match.group(2)}[REDACTED]", value
    )
    value = URL_CREDENTIAL_RE.sub(r"\1[REDACTED]:[REDACTED]@", value)
    value = SECRET_QUERY_RE.sub(r"\1[REDACTED]", value)
    value = BEARER_RE.sub("Bearer [REDACTED]", value)
    value = OPENAI_KEY_RE.sub("[REDACTED_OPENAI_KEY]", value)
    value = AWS_KEY_RE.sub("[REDACTED_AWS_KEY]", value)
    value = JWT_RE.sub("[REDACTED_JWT]", value)
    value = EMAIL_RE.sub("[REDACTED_EMAIL]", value)
    value = KOREAN_PHONE_RE.sub("[REDACTED_PHONE]", value)
    value = RESIDENT_ID_RE.sub("[REDACTED_RESIDENT_ID]", value)
    return IP_ADDRESS_RE.sub("[REDACTED_IP]", value)


def deidentify_payload(value: Any, *, depth: int = 0) -> Any:
    if depth > 30:
        raise UnsafeTrainingRecord("Training payload nesting exceeds the safety limit.")
    if isinstance(value, dict):
        result = {}
        for key, item in value.items():
            key_text = str(key)
            if SENSITIVE_FIELD_RE.search(key_text):
                continue
            result[key_text] = deidentify_payload(item, depth=depth + 1)
        return result
    if isinstance(value, list):
        return [deidentify_payload(item, depth=depth + 1) for item in value]
    if isinstance(value, str):
        return redact_sensitive_text(value)
    if value is None or isinstance(value, (bool, int, float)):
        return value
    raise UnsafeTrainingRecord(f"Unsupported JSON value type: {type(value).__name__}")


def build_export_record(candidate, export_format: str) -> dict[str, Any]:
    input_payload = deidentify_payload(candidate.input_payload)
    output_payload = deidentify_payload(
        candidate.chosen_output or candidate.output_payload
    )
    identity_source = json.dumps(
        {
            "task": candidate.training_task,
            "input": input_payload,
            "output": output_payload,
        },
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    example_id = f"sha256:{hashlib.sha256(identity_source).hexdigest()}"
    metadata = {
        "example_id": example_id,
        "training_task": candidate.training_task,
        "quality_score": candidate.quality_score,
    }

    if export_format == "hf_sft":
        record = {
            "schema_version": DATASET_SCHEMA_VERSION,
            "instruction": (
                "후보 공연 목록 안에서만 사용자의 요청과 취향에 맞는 공연을 추천하고, "
                "친근한 한국어로 추천 이유를 작성하세요."
            ),
            "input": json.dumps(
                input_payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            "output": json.dumps(
                output_payload,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ),
            "metadata": metadata,
        }
    else:
        record = {
            "schema_version": DATASET_SCHEMA_VERSION,
            "input": input_payload,
            "output": output_payload,
            "metadata": metadata,
        }

    encoded = json.dumps(
        record,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    if len(encoded) > MAX_RECORD_BYTES:
        raise UnsafeTrainingRecord(
            f"De-identified training record exceeds {MAX_RECORD_BYTES} bytes."
        )
    return record


class Command(BaseCommand):
    help = (
        "Export human-reviewed, approved and de-identified recommendation "
        "training examples into a versioned dataset directory. Dry-run is the default."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--format",
            choices=("neutral", "hf_sft"),
            default="neutral",
            help="Dataset record format (default: neutral).",
        )
        parser.add_argument(
            "--output-dir",
            help=(
                "Existing sibling repository directory. Relative paths are resolved "
                "from the backend root; writes require --apply."
            ),
        )
        parser.add_argument(
            "--dataset-version",
            help=(
                "Filesystem-safe dataset version. Defaults to the UTC export timestamp."
            ),
        )
        parser.add_argument(
            "--include-exported",
            action="store_true",
            help="Build a full approved snapshot including previously exported rows.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=DEFAULT_BATCH_SIZE,
            help=f"Database iterator/update batch size (default: {DEFAULT_BATCH_SIZE}).",
        )
        parser.add_argument(
            "--apply",
            action="store_true",
            help=(
                "Write the dataset and manifest, then mark newly exported candidates. "
                "Without this flag the command only reports the selection."
            ),
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        if not 1 <= batch_size <= MAX_BATCH_SIZE:
            raise CommandError(f"--batch-size must be between 1 and {MAX_BATCH_SIZE}.")

        dataset_version = options["dataset_version"] or timezone.now().strftime(
            "%Y%m%dT%H%M%SZ"
        )
        if not SAFE_VERSION_RE.fullmatch(dataset_version):
            raise CommandError(
                "--dataset-version must contain only letters, numbers, '.', '_' or '-'."
            )

        queryset = self._approved_queryset(options["include_exported"])
        candidate_count = queryset.count()
        mode = "APPLY" if options["apply"] else "DRY-RUN"
        self.stdout.write(
            f"{mode}: {candidate_count} approved candidate(s), "
            f"dataset_version={dataset_version}, format={options['format']}"
        )

        output_dir = None
        if options["output_dir"]:
            output_dir = self._safe_output_directory(options["output_dir"])
            self.stdout.write(f"Output repository: {output_dir}")

        if not options["apply"]:
            self.stdout.write(
                self.style.WARNING(
                    "Dry-run only: no files were created and no candidates were updated."
                )
            )
            return
        if output_dir is None:
            raise CommandError("--output-dir is required when --apply is used.")
        if candidate_count == 0:
            raise CommandError("No approved training examples matched the export criteria.")

        final_directory, exported_count = self._write_dataset(
            queryset=queryset,
            output_dir=output_dir,
            dataset_version=dataset_version,
            export_format=options["format"],
            include_exported=options["include_exported"],
            batch_size=batch_size,
        )
        self.stdout.write(
            self.style.SUCCESS(
                f"Exported {exported_count} approved example(s) to {final_directory}"
            )
        )

    @staticmethod
    def _approved_queryset(include_exported: bool):
        allowed_statuses = [TrainingExampleCandidate.Status.AUTO_APPROVED]
        if include_exported:
            allowed_statuses.append(TrainingExampleCandidate.Status.EXPORTED)
        queryset = TrainingExampleCandidate.objects.filter(
            approved_for_training=True,
            reviewed_by__isnull=False,
            reviewed_at__isnull=False,
            status__in=allowed_statuses,
        )
        if not include_exported:
            queryset = queryset.filter(exported_at__isnull=True)
        return queryset.order_by("pk")

    @staticmethod
    def _safe_output_directory(raw_path: str) -> Path:
        backend_root = Path(settings.BASE_DIR).resolve(strict=True)
        candidate = Path(raw_path).expanduser()
        if not candidate.is_absolute():
            candidate = backend_root / candidate
        try:
            output_dir = candidate.resolve(strict=True)
        except OSError as exc:
            raise CommandError("--output-dir must be an existing directory.") from exc

        if (
            candidate.is_symlink()
            or not output_dir.is_dir()
            or output_dir == backend_root
            or output_dir.parent != backend_root.parent
        ):
            raise CommandError(
                "--output-dir must be a real directory directly beside the backend "
                "project, not inside it."
            )
        return output_dir

    def _write_dataset(
        self,
        *,
        queryset,
        output_dir: Path,
        dataset_version: str,
        export_format: str,
        include_exported: bool,
        batch_size: int,
    ) -> tuple[Path, int]:
        dataset_root = output_dir / "datasets" / "recommendations"
        dataset_root.mkdir(parents=True, exist_ok=True)
        final_directory = dataset_root / dataset_version
        if final_directory.exists():
            raise CommandError(
                "The requested dataset version already exists; choose a new version."
            )

        temporary_directory = Path(
            tempfile.mkdtemp(prefix=".export-", dir=dataset_root)
        )
        id_file = tempfile.NamedTemporaryFile(
            mode="w",
            encoding="ascii",
            newline="\n",
            prefix=".candidate-ids-",
            suffix=".tmp",
            dir=output_dir,
            delete=False,
        )
        id_path = Path(id_file.name)
        exported_count = 0
        try:
            data_path = temporary_directory / "data.jsonl"
            digest = hashlib.sha256()
            with data_path.open("wb") as output:
                for candidate in queryset.iterator(chunk_size=batch_size):
                    try:
                        record = build_export_record(candidate, export_format)
                    except UnsafeTrainingRecord as exc:
                        raise CommandError(
                            "An approved candidate failed the export safety policy; "
                            "the dataset was not written."
                        ) from exc
                    encoded = json.dumps(
                        record,
                        ensure_ascii=False,
                        sort_keys=True,
                        separators=(",", ":"),
                    ).encode("utf-8") + b"\n"
                    output.write(encoded)
                    digest.update(encoded)
                    id_file.write(f"{candidate.pk}\n")
                    exported_count += 1
                output.flush()
                os.fsync(output.fileno())
            id_file.flush()
            os.fsync(id_file.fileno())
            id_file.close()

            if exported_count == 0:
                raise CommandError(
                    "No approved training examples remained at export time."
                )

            generated_at = timezone.now().astimezone(UTC).isoformat()
            manifest = {
                "schema_version": MANIFEST_SCHEMA_VERSION,
                "dataset": DATASET_NAME,
                "dataset_version": dataset_version,
                "generated_at": generated_at,
                "record_format": export_format,
                "selection": {
                    "approved_for_training": True,
                    "human_review_required": True,
                    "allowed_statuses": (
                        ["auto_approved", "exported"]
                        if include_exported
                        else ["auto_approved"]
                    ),
                    "include_previously_exported": include_exported,
                },
                "deidentification": {
                    "policy_version": DEIDENTIFICATION_POLICY_VERSION,
                    "removed_fields": (
                        "account identifiers, contact fields, addresses, "
                        "credentials and session identifiers"
                    ),
                    "redacted_patterns": (
                        "email, Korean phone number, resident registration number, "
                        "IP address and common credential formats"
                    ),
                },
                "files": [
                    {
                        "path": "data.jsonl",
                        "records": exported_count,
                        "bytes": data_path.stat().st_size,
                        "sha256": digest.hexdigest(),
                    }
                ],
            }
            manifest_path = temporary_directory / "manifest.json"
            with manifest_path.open("w", encoding="utf-8", newline="\n") as output:
                json.dump(
                    manifest,
                    output,
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                )
                output.write("\n")
                output.flush()
                os.fsync(output.fileno())

            os.replace(temporary_directory, final_directory)
            self._mark_candidates_exported(id_path, batch_size)
            return final_directory, exported_count
        finally:
            if not id_file.closed:
                id_file.close()
            id_path.unlink(missing_ok=True)
            if temporary_directory.exists():
                shutil.rmtree(temporary_directory)

    @staticmethod
    def _mark_candidates_exported(id_path: Path, batch_size: int):
        exported_at = timezone.now()
        id_batch = []
        with id_path.open("r", encoding="ascii") as source:
            for line in source:
                id_batch.append(int(line))
                if len(id_batch) >= batch_size:
                    Command._update_candidate_batch(id_batch, exported_at)
                    id_batch.clear()
        if id_batch:
            Command._update_candidate_batch(id_batch, exported_at)

    @staticmethod
    def _update_candidate_batch(ids: list[int], exported_at):
        TrainingExampleCandidate.objects.filter(
            pk__in=ids,
            approved_for_training=True,
            reviewed_by__isnull=False,
            reviewed_at__isnull=False,
            status=TrainingExampleCandidate.Status.AUTO_APPROVED,
            exported_at__isnull=True,
        ).update(
            status=TrainingExampleCandidate.Status.EXPORTED,
            exported_at=exported_at,
        )
