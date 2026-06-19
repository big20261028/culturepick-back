import json
from pathlib import Path

from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.recommendations.models import TrainingExampleCandidate


class Command(BaseCommand):
    help = "Export approved recommendation training examples as JSONL."

    def add_arguments(self, parser):
        parser.add_argument(
            "--format",
            choices=("neutral", "hf_sft"),
            default="neutral",
            help="Export format. neutral keeps input/output objects; hf_sft writes instruction/input/output strings.",
        )
        parser.add_argument(
            "--output",
            required=True,
            help="Output JSONL file path.",
        )
        parser.add_argument(
            "--include-review",
            action="store_true",
            default=False,
            help="Include needs_review candidates as well as approved candidates.",
        )
        parser.add_argument(
            "--mark-exported",
            action="store_true",
            default=False,
            help="Mark exported candidates as exported.",
        )
        parser.add_argument(
            "--include-exported",
            action="store_true",
            default=False,
            help="Include candidates that were already exported.",
        )

    def handle(self, *args, **options):
        output_path = Path(options["output"])
        if not output_path.parent.exists():
            output_path.parent.mkdir(parents=True, exist_ok=True)

        queryset = TrainingExampleCandidate.objects.filter(approved_for_training=True)
        if options["include_review"]:
            queryset = TrainingExampleCandidate.objects.filter(
                status__in=[
                    TrainingExampleCandidate.Status.AUTO_APPROVED,
                    TrainingExampleCandidate.Status.NEEDS_REVIEW,
                ]
            )
        if not options["include_exported"]:
            queryset = queryset.exclude(
                status=TrainingExampleCandidate.Status.EXPORTED,
            ).filter(exported_at__isnull=True)

        queryset = queryset.order_by("id")
        if not queryset.exists():
            raise CommandError("No training examples matched the export criteria.")

        exported_ids = []
        with output_path.open("w", encoding="utf-8") as output_file:
            for candidate in queryset:
                record = self._build_record(candidate, options["format"])
                output_file.write(json.dumps(record, ensure_ascii=False) + "\n")
                exported_ids.append(candidate.id)

        if options["mark_exported"]:
            TrainingExampleCandidate.objects.filter(id__in=exported_ids).update(
                status=TrainingExampleCandidate.Status.EXPORTED,
                exported_at=timezone.now(),
            )

        self.stdout.write(self.style.SUCCESS(f"exported {len(exported_ids)} examples to {output_path}"))

    def _build_record(self, candidate, export_format):
        if export_format == "hf_sft":
            return {
                "instruction": (
                    "후보 공연 목록 안에서만 사용자의 요청과 취향에 맞는 공연을 추천하고, "
                    "친근한 한국어로 추천 이유를 작성하세요."
                ),
                "input": json.dumps(candidate.input_payload, ensure_ascii=False),
                "output": json.dumps(candidate.output_payload, ensure_ascii=False),
                "metadata": {
                    "source_session_id": candidate.source_session_id,
                    "quality_score": candidate.quality_score,
                    "status": candidate.status,
                    "training_task": candidate.training_task,
                },
            }

        return {
            "input": candidate.input_payload,
            "output": candidate.output_payload,
            "metadata": {
                "source_session_id": candidate.source_session_id,
                "quality_score": candidate.quality_score,
                "status": candidate.status,
                "training_task": candidate.training_task,
            },
        }
