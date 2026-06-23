from django.core.management.base import BaseCommand

from apps.performances.kopis.sync import parse_price_options
from apps.performances.models import Performance, PerformancePrice


class Command(BaseCommand):
    help = "Rebuild structured performance price options from stored price_info."

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Show how many rows would be rebuilt without saving.",
        )
        parser.add_argument(
            "--limit",
            type=int,
            default=0,
            help="Maximum number of performances to inspect. Default is all rows.",
        )

    def handle(self, *args, **options):
        dry_run = options["dry_run"]
        limit = options["limit"]

        queryset = (
            Performance.objects.exclude(price_info="")
            .only("performance_id", "title", "price_info")
            .order_by("performance_id")
        )
        if limit > 0:
            queryset = queryset[:limit]

        inspected = 0
        rebuilt = 0
        created = 0
        for performance in queryset.iterator():
            inspected += 1
            options_data = parse_price_options(performance.price_info)
            if not options_data:
                continue

            rebuilt += 1
            created += len(options_data)
            self.stdout.write(
                f"{performance.performance_id} {performance.title}: {len(options_data)} option(s)"
            )

            if dry_run:
                continue

            PerformancePrice.objects.filter(performance=performance).delete()
            PerformancePrice.objects.bulk_create(
                [
                    PerformancePrice(
                        performance=performance,
                        label=option["label"],
                        price=option["price"],
                        currency=option["currency"],
                        raw_text=option["raw_text"],
                        sort_order=idx,
                    )
                    for idx, option in enumerate(options_data)
                ]
            )

        action = "would_rebuild" if dry_run else "rebuilt"
        self.stdout.write(
            self.style.SUCCESS(
                f"done: inspected={inspected} {action}={rebuilt} price_options={created}"
            )
        )
