"""
초기 데이터 적재 커맨드.

사용법::

    # 기본: 올해 전체 연극+뮤지컬 수집
    python manage.py sync_kopis

    # 기간 지정
    python manage.py sync_kopis --stdate 20230101 --eddate 20231231

    # 특정 장르만 (연극)
    python manage.py sync_kopis --genre AAAA

    # 공연시설만 수집
    python manage.py sync_kopis --venues-only

    # 공연시설 먼저 수집 후 공연 수집 (권장)
    python manage.py sync_kopis --with-venues
"""
from __future__ import annotations

import logging
from datetime import date

from django.core.management.base import BaseCommand, CommandError

from apps.performances.kopis.client import GenreCode, KopisClient
from apps.performances.kopis.sync import (
    SyncResult,
    sync_all_venues,
    sync_performances_in_range,
)

logger = logging.getLogger(__name__)

ALL_GENRES = [
    GenreCode.PLAY,
    GenreCode.MUSICAL,
    GenreCode.CLASSICAL,
    GenreCode.DANCE,
    GenreCode.POPULAR_MUSIC,
]


class Command(BaseCommand):
    help = "KOPIS API에서 공연 데이터를 수집해 DB에 적재합니다."

    def add_arguments(self, parser):
        today = date.today()
        parser.add_argument(
            "--stdate",
            default=f"{today.year}0101",
            help="start date YYYYMMDD",
        )
        parser.add_argument(
            "--eddate",
            default=f"{today.year}1231",
            help="end date YYYYMMDD",
        )
        parser.add_argument(
            "--genre",
            default=None,
            help=(
                "genre code (AAAA=play GGGA=musical CCCA=classic "
                "CCCC=korean_music CCCD=popular_music BBBC=dance)"
            ),
        )
        parser.add_argument(
            "--with-venues",
            action="store_true",
            default=False,
            help="sync venues first",
        )
        parser.add_argument(
            "--venues-only",
            action="store_true",
            default=False,
            help="sync venues only",
        )

    def handle(self, *args, **options):
        stdate = options["stdate"]
        eddate = options["eddate"]
        genre = options["genre"]
        with_venues = options["with_venues"]
        venues_only = options["venues_only"]

        if len(stdate) != 8 or not stdate.isdigit():
            raise CommandError(f"invalid stdate: {stdate}")
        if len(eddate) != 8 or not eddate.isdigit():
            raise CommandError(f"invalid eddate: {eddate}")

        client = KopisClient()

        if with_venues or venues_only:
            self.stdout.write("syncing venues...")
            venue_result = sync_all_venues(client)
            self.stdout.write(self.style.SUCCESS(f"venues done: {venue_result}"))

        if venues_only:
            return

        genres = [genre] if genre else ALL_GENRES
        total = SyncResult()

        self.stdout.write(f"syncing performances ({stdate} ~ {eddate})...")

        for g in genres:
            self.stdout.write(f"  genre [{g}]...", ending="")
            try:
                result = sync_performances_in_range(
                    stdate=stdate,
                    eddate=eddate,
                    genre=g,
                    client=client,
                )
                total = total + result
                self.stdout.write(self.style.SUCCESS(f" done ({result})"))
            except Exception as exc:
                self.stdout.write(self.style.ERROR(f" error: {exc}"))
                logger.error("genre %s error: %s", g, exc, exc_info=True)

        self.stdout.write(
            self.style.SUCCESS(
                f"\ncreated {total.created} / updated {total.updated} / "
                f"skipped {total.skipped} / errors {total.errors}"
            )
        )
