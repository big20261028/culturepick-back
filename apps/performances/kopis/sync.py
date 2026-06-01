"""
KOPIS 동기화 서비스.

API에서 받아온 Raw DTO를 DB 모델로 변환·저장합니다.
update_or_create 패턴을 사용해 멱등성을 보장합니다.
"""

from __future__ import annotations

import logging
from decimal import Decimal, InvalidOperation
from typing import NamedTuple

from django.db import transaction
from django.utils import timezone

from ..models import BookingLink, Performance, PerformanceImage, Venue
from .client import KopisClient, RawPerformanceDetail, RawVenueDetail
from .parser import to_date

logger = logging.getLogger(__name__)


# ── 결과 집계 ──────────────────────────────────────────────────────────────────

class SyncResult(NamedTuple):
    created: int = 0
    updated: int = 0
    skipped: int = 0
    errors: int = 0

    def __add__(self, other: "SyncResult") -> "SyncResult":
        return SyncResult(
            created=self.created + other.created,
            updated=self.updated + other.updated,
            skipped=self.skipped + other.skipped,
            errors=self.errors + other.errors,
        )

    def __str__(self) -> str:
        return (
            f"생성 {self.created} / 갱신 {self.updated} / "
            f"스킵 {self.skipped} / 오류 {self.errors}"
        )


# ── 공연시설 동기화 ────────────────────────────────────────────────────────────

def _decimal_or_none(raw: str) -> Decimal | None:
    """좌표 문자열 → Decimal 변환. 변환 실패 시 None."""
    try:
        return Decimal(raw) if raw else None
    except InvalidOperation:
        return None


def _int_or_none(raw: str) -> int | None:
    try:
        return int(raw) if raw else None
    except ValueError:
        return None


def sync_venue(raw: RawVenueDetail) -> tuple[Venue, bool]:
    """
    단일 공연시설을 DB에 upsert.
    반환값: (Venue 인스턴스, 신규생성 여부)
    """
    venue, created = Venue.objects.update_or_create(
        venue_id=raw.mt10id,
        defaults={
            "name": raw.fcltynm,
            "sido": raw.sidonm,
            "gugun": raw.gugunnm,
            "address": raw.adres,
            "latitude": _decimal_or_none(raw.la),
            "longitude": _decimal_or_none(raw.lo),
            "seat_scale": _int_or_none(raw.seatscale),
            "synced_at": timezone.now(),
        },
    )
    action = "생성" if created else "갱신"
    logger.debug("[Sync] 공연시설 %s: %s (%s)", action, raw.fcltynm, raw.mt10id)
    return venue, created


def sync_all_venues(client: KopisClient | None = None) -> SyncResult:
    """
    KOPIS 공연시설 전체를 동기화합니다.
    공연 동기화 전에 실행해서 FK 참조를 준비하세요.
    """
    if client is None:
        client = KopisClient()

    result = SyncResult()
    for mt10id in client.iter_venues():
        try:
            raw = client.get_venue_detail(mt10id)
            if raw is None or not raw.mt10id:
                result = result._replace(skipped=result.skipped + 1)
                continue
            _, created = sync_venue(raw)
            if created:
                result = result._replace(created=result.created + 1)
            else:
                result = result._replace(updated=result.updated + 1)
        except Exception as exc:
            logger.error("[Sync] 공연시설 오류 mt10id=%s: %s", mt10id, exc)
            result = result._replace(errors=result.errors + 1)

    logger.info("[Sync] 공연시설 동기화 완료: %s", result)
    return result


# ── 공연 동기화 ────────────────────────────────────────────────────────────────

def _get_or_fetch_venue(mt10id: str, client: KopisClient) -> Venue | None:
    """
    DB에 시설이 있으면 반환, 없으면 API에서 가져와 저장 후 반환.
    mt10id가 비어 있으면 None 반환.
    """
    if not mt10id:
        return None
    try:
        return Venue.objects.get(venue_id=mt10id)
    except Venue.DoesNotExist:
        pass

    raw = client.get_venue_detail(mt10id)
    if raw is None:
        return None
    venue, _ = sync_venue(raw)
    return venue


@transaction.atomic
def sync_performance(raw: RawPerformanceDetail, client: KopisClient) -> tuple[Performance, bool]:
    """
    단일 공연을 DB에 upsert.
    소개이미지·예매링크는 전체 교체(delete → bulk_create).
    """
    venue = _get_or_fetch_venue(raw.mt10id, client)

    perf, created = Performance.objects.update_or_create(
        performance_id=raw.mt20id,
        defaults={
            "title": raw.prfnm,
            "genre": raw.genrenm,
            "start_date": to_date(raw.prfpdfrom),
            "end_date": to_date(raw.prfpdto),
            "status": raw.prfstate,
            "cast": raw.prfcast,
            "crew": raw.prfcrew,
            "runtime": raw.prfruntime,
            "age_rating": raw.prfage,
            "synopsis": raw.sty,
            "price_info": raw.pcseguidance,
            "schedule_info": raw.dtguidance,
            "poster_url": raw.poster,
            "venue": venue,
            "synced_at": timezone.now(),
        },
    )

    # ── 소개 이미지: 전체 교체 ──────────────────────────────────────────────
    PerformanceImage.objects.filter(performance=perf).delete()
    if raw.styurls:
        PerformanceImage.objects.bulk_create(
            [
                PerformanceImage(performance=perf, image_url=url, sort_order=idx)
                for idx, url in enumerate(raw.styurls)
            ]
        )

    # ── 예매 링크: 전체 교체 ───────────────────────────────────────────────
    BookingLink.objects.filter(performance=perf).delete()
    if raw.relates:
        BookingLink.objects.bulk_create(
            [
                BookingLink(
                    performance=perf,
                    site_name=r["site_name"],
                    url=r["url"],
                )
                for r in raw.relates
            ]
        )

    action = "생성" if created else "갱신"
    logger.debug(
        "[Sync] 공연 %s: %s (%s) 이미지=%d 예매처=%d",
        action, raw.prfnm, raw.mt20id,
        len(raw.styurls), len(raw.relates),
    )
    return perf, created


def sync_performances_in_range(
    stdate: str,
    eddate: str,
    genre: str | None = None,
    prfstate: str | None = None,
    client: KopisClient | None = None,
) -> SyncResult:
    """
    특정 기간·장르·상태의 공연을 동기화합니다.

    :param stdate:   시작일 YYYYMMDD
    :param eddate:   종료일 YYYYMMDD
    :param genre:    장르코드 (None = 전체)
    :param prfstate: 공연상태 (None = 전체)

    사용 예::

        result = sync_performances_in_range(
            stdate="20240101",
            eddate="20241231",
            genre=GenreCode.MUSICAL,
        )
        print(result)  # 생성 120 / 갱신 45 / 스킵 0 / 오류 2
    """
    if client is None:
        client = KopisClient()

    result = SyncResult()
    for raw_list in client.iter_performances(stdate, eddate, genre, prfstate):
        try:
            detail = client.get_performance_detail(raw_list.mt20id)
            if detail is None:
                logger.warning("[Sync] 공연상세 없음: %s", raw_list.mt20id)
                result = result._replace(skipped=result.skipped + 1)
                continue

            _, created = sync_performance(detail, client)
            if created:
                result = result._replace(created=result.created + 1)
            else:
                result = result._replace(updated=result.updated + 1)

        except Exception as exc:
            logger.error(
                "[Sync] 공연 동기화 오류 mt20id=%s title=%s: %s",
                raw_list.mt20id, raw_list.prfnm, exc,
                exc_info=True,
            )
            result = result._replace(errors=result.errors + 1)

    logger.info(
        "[Sync] 공연 동기화 완료 (%s ~ %s genre=%s): %s",
        stdate, eddate, genre or "전체", result,
    )
    return result
