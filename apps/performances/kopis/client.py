from __future__ import annotations

import logging
import time
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Iterator
from urllib.parse import urljoin

import requests
from django.conf import settings

logger = logging.getLogger(__name__)

BASE_URL = "http://www.kopis.or.kr/openApi/restful/"
DEFAULT_ROWS = 100
REQUEST_TIMEOUT = 10
RETRY_COUNT = 3
RETRY_BACKOFF = 2.0
REQUEST_INTERVAL = 0.2
MAX_DATE_RANGE_DAYS = 31


class GenreCode:
    PLAY          = "AAAA"  # 연극
    MUSICAL       = "GGGA"  # 뮤지컬
    CLASSICAL     = "CCCA"  # 서양음악(클래식)
    KOREAN_MUSIC  = "CCCC"  # 한국음악(국악)
    POPULAR_MUSIC = "CCCD"  # 대중음악
    DANCE         = "BBBC"  # 무용(서양/한국무용)
    POPULAR_DANCE = "BBBE"  # 대중무용
    CIRCUS        = "EEEB"  # 서커스/마술
    MIXED         = "EEEA"  # 복합


class PrfState:
    UPCOMING  = "01"  # 공연예정
    ONGOING   = "02"  # 공연중
    COMPLETED = "03"  # 공연완료


@dataclass
class RawPerformanceList:
    mt20id: str
    prfnm: str
    prfpdfrom: str
    prfpdto: str
    fcltynm: str
    poster: str
    genrenm: str
    prfstate: str
    openrun: str


@dataclass
class RawPerformanceDetail:
    mt20id: str
    prfnm: str
    prfpdfrom: str
    prfpdto: str
    fcltynm: str
    mt10id: str
    prfcast: str
    prfcrew: str
    prfruntime: str
    prfage: str
    sty: str
    pcseguidance: str
    genrenm: str
    prfstate: str
    poster: str
    area: str
    dtguidance: str
    styurls: list[str] = field(default_factory=list)
    relates: list[dict] = field(default_factory=list)


@dataclass
class RawVenueDetail:
    mt10id: str
    fcltynm: str
    sidonm: str
    gugunnm: str
    adres: str
    la: str
    lo: str
    seatscale: str


def _split_date_range(stdate: str, eddate: str) -> list[tuple[str, str]]:
    """
    31일 제한을 넘는 기간을 31일 단위로 분할합니다.

    예) 20260101 ~ 20261231 → [(20260101, 20260131), (20260201, 20260228), ...]
    """
    start = date(int(stdate[:4]), int(stdate[4:6]), int(stdate[6:8]))
    end   = date(int(eddate[:4]), int(eddate[4:6]), int(eddate[6:8]))

    chunks = []
    cursor = start
    while cursor <= end:
        chunk_end = min(cursor + timedelta(days=MAX_DATE_RANGE_DAYS - 1), end)
        chunks.append((cursor.strftime("%Y%m%d"), chunk_end.strftime("%Y%m%d")))
        cursor = chunk_end + timedelta(days=1)
    return chunks


class KopisClient:

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = api_key or settings.KOPIS_API_KEY
        self.session = requests.Session()
        self.session.headers.update({"Accept": "application/xml"})

    def _get(self, path: str, params: dict) -> bytes:
        url = urljoin(BASE_URL, path)
        params["service"] = self.api_key

        for attempt in range(1, RETRY_COUNT + 1):
            try:
                resp = self.session.get(url, params=params, timeout=REQUEST_TIMEOUT)
                resp.raise_for_status()
                time.sleep(REQUEST_INTERVAL)
                return resp.content
            except requests.RequestException as exc:
                wait = RETRY_BACKOFF ** attempt
                logger.warning(
                    "[KOPIS] request failed (attempt %d/%d) url=%s error=%s",
                    attempt, RETRY_COUNT, url, exc,
                )
                if attempt == RETRY_COUNT:
                    raise
                time.sleep(wait)

    def iter_performances(
        self,
        stdate: str,
        eddate: str,
        genre: str | None = None,
        prfstate: str | None = None,
        rows: int = DEFAULT_ROWS,
    ) -> Iterator[RawPerformanceList]:
        """
        31일 제한을 자동으로 처리해서 전체 기간을 순회합니다.
        """
        from .parser import parse_performance_list

        for chunk_start, chunk_end in _split_date_range(stdate, eddate):
            page = 1
            while True:
                params: dict = {
                    "stdate": chunk_start,
                    "eddate": chunk_end,
                    "cpage": page,
                    "rows": rows,
                }
                if genre:
                    params["shcate"] = genre
                if prfstate:
                    params["prfstate"] = prfstate

                logger.info(
                    "[KOPIS] performances list: page=%d %s~%s genre=%s",
                    page, chunk_start, chunk_end, genre or "all",
                )
                xml_bytes = self._get("pblprfr", params)
                items = parse_performance_list(xml_bytes)

                if not items:
                    break

                yield from items

                if len(items) < rows:
                    break
                page += 1

    def get_performance_detail(self, mt20id: str) -> RawPerformanceDetail | None:
        from .parser import parse_performance_detail
        logger.debug("[KOPIS] performance detail: mt20id=%s", mt20id)
        xml_bytes = self._get(f"pblprfr/{mt20id}", {})
        return parse_performance_detail(xml_bytes)

    def iter_venues(self, rows: int = DEFAULT_ROWS) -> Iterator[str]:
        from .parser import parse_venue_list
        page = 1
        while True:
            params = {"cpage": page, "rows": rows}
            logger.info("[KOPIS] venues list: page=%d", page)
            xml_bytes = self._get("prfplc", params)
            ids = parse_venue_list(xml_bytes)
            if not ids:
                break
            yield from ids
            if len(ids) < rows:
                break
            page += 1

    def get_venue_detail(self, mt10id: str) -> RawVenueDetail | None:
        from .parser import parse_venue_detail
        logger.debug("[KOPIS] venue detail: mt10id=%s", mt10id)
        xml_bytes = self._get(f"prfplc/{mt10id}", {})
        return parse_venue_detail(xml_bytes)
