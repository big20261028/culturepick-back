from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.community.html_sanitizer import (
    has_meaningful_html_content,
    sanitize_post_html,
)
from apps.community.models import Post


class Command(BaseCommand):
    help = (
        "Inspect existing HTML community posts and optionally replace unsafe HTML. "
        "The default mode is read-only."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--apply",
            action="store_true",
            help="Persist sanitized HTML. Without this flag, no rows are changed.",
        )
        parser.add_argument(
            "--batch-size",
            type=int,
            default=500,
            help="Database iterator chunk size (default: 500).",
        )
        parser.add_argument(
            "--limit",
            type=int,
            help="Inspect at most this many posts.",
        )

    def handle(self, *args, **options):
        batch_size = options["batch_size"]
        limit = options["limit"]
        if batch_size < 1:
            raise CommandError("--batch-size must be at least 1.")
        if limit is not None and limit < 1:
            raise CommandError("--limit must be at least 1.")

        queryset = (
            Post.objects.filter(content_format=Post.ContentFormat.HTML)
            .only("id", "content")
            .order_by("id")
        )
        if limit is not None:
            queryset = queryset[:limit]

        scanned = 0
        changed = 0
        applied = 0
        manual_review = 0
        manual_review_ids = []
        concurrent_changes = 0
        concurrent_change_ids = []

        for post in queryset.iterator(chunk_size=batch_size):
            scanned += 1
            sanitized_content = sanitize_post_html(post.content)
            if sanitized_content == post.content:
                continue

            changed += 1
            if not has_meaningful_html_content(sanitized_content):
                manual_review += 1
                if len(manual_review_ids) < 20:
                    manual_review_ids.append(post.pk)
                continue

            if options["apply"]:
                updated = Post.objects.filter(
                    pk=post.pk,
                    content=post.content,
                ).update(
                    content=sanitized_content,
                    updated_at=timezone.now(),
                )
                applied += updated
                if not updated:
                    concurrent_changes += 1
                    if len(concurrent_change_ids) < 20:
                        concurrent_change_ids.append(post.pk)

        mode = "apply" if options["apply"] else "dry-run"
        self.stdout.write(
            f"mode={mode} scanned={scanned} changed={changed} applied={applied} "
            f"manual_review={manual_review} "
            f"concurrent_changes={concurrent_changes}"
        )
        if manual_review_ids:
            self.stdout.write(
                "manual review required for posts whose sanitized body is empty: "
                + ",".join(str(post_id) for post_id in manual_review_ids[:20])
            )
        if concurrent_change_ids:
            self.stdout.write(
                "skipped posts changed during the command: "
                + ",".join(str(post_id) for post_id in concurrent_change_ids[:20])
            )
