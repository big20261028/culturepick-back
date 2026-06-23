"""
Celery 태스크 - KOPIS 데이터 주기적 동기화.

sync_single_performance.delay("PF12345")
추후 프론트에서 주기적으로 서버에 조회를 하게 하거나
웹소켓(asgi.py)를 통해 서버가 프론트에게 다시 보내주는 기술 추가


celery.py / settings.py 설정 예::

    # settings.py
    CELERY_BEAT_SCHEDULE = {
        "sync-ongoing-performances": {
            "task": "performances.tasks.sync_ongoing_performances",
            "schedule": crontab(hour=4, minute=0),   # 매일 새벽 4시
        },
        "sync-upcoming-performances": {
            "task": "performances.tasks.sync_upcoming_performances",
            "schedule": crontab(hour=4, minute=30),  # 매일 새벽 4시 30분
        },
    }
"""

from __future__ import annotations

import logging
from datetime import date, timedelta

from celery import shared_task
from django.core.management import call_command
from django.utils import timezone

from apps.performances.kopis.client import GenreCode, KopisClient, PrfState
from apps.performances.kopis.sync import SyncResult, sync_performances_in_range

logger = logging.getLogger(__name__)

TARGET_GENRES = [
    GenreCode.PLAY,
    GenreCode.MUSICAL,
    GenreCode.CLASSICAL,
    GenreCode.KOREAN_MUSIC,
    GenreCode.DANCE,
    GenreCode.POPULAR_MUSIC,
]


@shared_task(name="apps.performances.tasks.ping_task")
def ping_task():
    logger.info("celery ping task received")
    return {
        "status": "ok",
        "message": "pong",
        "finished_at": timezone.now().isoformat(),
    }


@shared_task(
    bind=True,
    max_retries=1,
    name="apps.performances.tasks.sync_kopis_task",
)
def sync_kopis_task(self, stdate, eddate, genre=None, with_venues=True):
    try:
        options = {
            "stdate": stdate,
            "eddate": eddate,
            "with_venues": with_venues,
        }
        if genre:
            options["genre"] = genre

        call_command("sync_kopis", **options)
        return {
            "status": "ok",
            "stdate": stdate,
            "eddate": eddate,
            "genre": genre,
            "with_venues": with_venues,
            "finished_at": timezone.now().isoformat(),
        }
    except Exception as exc:
        logger.error("sync_kopis_task error: %s", exc, exc_info=True)
        raise self.retry(exc=exc)


def _date_range(days_before=0, days_after=90):
    today = date.today()
    stdate = (today - timedelta(days=days_before)).strftime("%Y%m%d")
    eddate = (today + timedelta(days=days_after)).strftime("%Y%m%d")
    return stdate, eddate


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="apps.performances.tasks.sync_ongoing_performances",
)
def sync_ongoing_performances(self):
    stdate, eddate = _date_range(days_before=0, days_after=90)
    client = KopisClient()
    total = SyncResult()

    for genre in TARGET_GENRES:
        try:
            result = sync_performances_in_range(
                stdate=stdate,
                eddate=eddate,
                genre=genre,
                prfstate=PrfState.ONGOING,
                client=client,
            )
            total = total + result
        except Exception as exc:
            logger.error("sync_ongoing error genre=%s: %s", genre, exc, exc_info=True)
            raise self.retry(exc=exc)

    logger.info("sync_ongoing done: %s", total)
    return {
        "task": "sync_ongoing_performances",
        "range": f"{stdate}~{eddate}",
        "created": total.created,
        "updated": total.updated,
        "errors": total.errors,
        "finished_at": timezone.now().isoformat(),
    }


@shared_task(
    bind=True,
    max_retries=3,
    default_retry_delay=60,
    name="apps.performances.tasks.sync_upcoming_performances",
)
def sync_upcoming_performances(self):
    stdate, eddate = _date_range(days_before=0, days_after=180)
    client = KopisClient()
    total = SyncResult()

    for genre in TARGET_GENRES:
        try:
            result = sync_performances_in_range(
                stdate=stdate,
                eddate=eddate,
                genre=genre,
                prfstate=PrfState.UPCOMING,
                client=client,
            )
            total = total + result
        except Exception as exc:
            logger.error("sync_upcoming error genre=%s: %s", genre, exc, exc_info=True)
            raise self.retry(exc=exc)

    logger.info("sync_upcoming done: %s", total)
    return {
        "task": "sync_upcoming_performances",
        "range": f"{stdate}~{eddate}",
        "created": total.created,
        "updated": total.updated,
        "errors": total.errors,
        "finished_at": timezone.now().isoformat(),
    }


@shared_task(
    bind=True,
    max_retries=2,
    name="apps.performances.tasks.sync_single_performance",
)
def sync_single_performance(self, performance_id):
    from apps.performances.kopis.sync import sync_performance

    client = KopisClient()
    try:
        detail = client.get_performance_detail(performance_id)
        if detail is None:
            return {"status": "not_found", "performance_id": performance_id}

        _, created = sync_performance(detail, client)
        return {
            "status": "created" if created else "updated",
            "performance_id": performance_id,
            "finished_at": timezone.now().isoformat(),
        }
    except Exception as exc:
        logger.error("sync_single error %s: %s", performance_id, exc, exc_info=True)
        raise self.retry(exc=exc)
