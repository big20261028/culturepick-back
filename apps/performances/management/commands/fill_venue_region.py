from django.core.management.base import BaseCommand
from django.db.models import Q

from apps.performances.models import Venue
from apps.performances.utils.address import (
    UNKNOWN_REGION_VALUES,
    is_blank_region_value,
    parse_sido_gugun,
)


class Command(BaseCommand):
    help = "Fill venue sido/gugun from address."

    def add_arguments(self, parser):
        parser.add_argument(
            "--overwrite",
            action="store_true",
            help="Recalculate and overwrite existing sido/gugun values.",
        )

    def handle(self, *args, **options):
        overwrite = options["overwrite"]
        if overwrite:
            venues = Venue.objects.all()
        else:
            venues = Venue.objects.filter(
                Q(sido__in=UNKNOWN_REGION_VALUES)
                | Q(gugun="")
                | Q(gugun="-")
                | Q(sido__isnull=True)
                | Q(gugun__isnull=True)
            )

        total = venues.count()
        self.stdout.write(f"target: {total}")

        updated = 0
        skipped = 0

        for venue in venues.iterator():
            parsed_sido, parsed_gugun = parse_sido_gugun(venue.address)
            fields = []

            if not parsed_sido:
                if is_blank_region_value(venue.sido):
                    venue.sido = "미분류"
                    venue.gugun = ""
                    fields = ["sido", "gugun"]
                else:
                    skipped += 1
                    continue
            else:
                if overwrite or is_blank_region_value(venue.sido):
                    venue.sido = parsed_sido
                    fields.append("sido")
                if overwrite or is_blank_region_value(venue.gugun):
                    venue.gugun = parsed_gugun
                    fields.append("gugun")

            if fields:
                venue.save(update_fields=sorted(set(fields)))
                updated += 1
            else:
                skipped += 1

        self.stdout.write(
            self.style.SUCCESS(f"done: updated={updated} skipped={skipped}")
        )
