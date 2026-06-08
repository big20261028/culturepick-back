"""
KOPIS API XML 응답 파서.

KOPIS는 XML을 반환합니다. ElementTree로 파싱 후
client.py 의 Raw DTO로 변환합니다.
"""

from __future__ import annotations

import logging
from datetime import date
from xml.etree import ElementTree as ET

from .client import (
    RawPerformanceDetail,
    RawPerformanceList,
    RawVenueDetail,
)

logger = logging.getLogger(__name__)


# ── 유틸 ───────────────────────────────────────────────────────────────────────

def _text(element: ET.Element | None, tag: str, default: str = "") -> str:
    """XML 요소에서 텍스트를 안전하게 추출."""
    if element is None:
        return default
    node = element.find(tag)
    return (node.text or "").strip() if node is not None else default


def _parse_kopis_date(raw: str) -> date | None:
    """
    KOPIS 날짜 문자열(YYYY.MM.DD 또는 YYYYMMDD)을 date 객체로 변환.

    >>> _parse_kopis_date("2024.03.15")
    datetime.date(2024, 3, 15)
    >>> _parse_kopis_date("20240315")
    datetime.date(2024, 3, 15)
    """
    if not raw:
        return None
    clean = raw.replace(".", "").strip()
    if len(clean) != 8 or not clean.isdigit():
        logger.warning("[KOPIS Parser] 날짜 파싱 실패: %r", raw)
        return None
    return date(int(clean[:4]), int(clean[4:6]), int(clean[6:8]))


def _safe_root(xml_bytes: bytes) -> ET.Element | None:
    """XML 바이트를 파싱해 루트 요소 반환. 실패 시 None."""
    try:
        return ET.fromstring(xml_bytes)
    except ET.ParseError as exc:
        logger.error("[KOPIS Parser] XML 파싱 오류: %s", exc)
        return None


# ── 공연목록 파서 ───────────────────────────────────────────────────────────────

def parse_performance_list(xml_bytes: bytes) -> list[RawPerformanceList]:
    """
    공연목록 API(pblprfr) 응답 파싱.

    응답 예시::

        <dbs>
          <db>
            <mt20id>PF123456</mt20id>
            <prfnm>레미제라블</prfnm>
            <prfpdfrom>2024.01.01</prfpdfrom>
            <prfpdto>2024.06.30</prfpdto>
            <fcltynm>블루스퀘어 신한카드홀</fcltynm>
            <poster>http://...poster.jpg</poster>
            <genrenm>뮤지컬</genrenm>
            <prfstate>공연중</prfstate>
            <openrun>N</openrun>
          </db>
        </dbs>
    """
    root = _safe_root(xml_bytes)
    if root is None:
        return []

    result: list[RawPerformanceList] = []
    for db in root.findall("db"):
        mt20id = _text(db, "mt20id")
        if not mt20id:
            continue
        result.append(
            RawPerformanceList(
                mt20id=mt20id,
                prfnm=_text(db, "prfnm"),
                prfpdfrom=_text(db, "prfpdfrom"),
                prfpdto=_text(db, "prfpdto"),
                fcltynm=_text(db, "fcltynm"),
                poster=_text(db, "poster"),
                genrenm=_text(db, "genrenm"),
                prfstate=_text(db, "prfstate"),
                openrun=_text(db, "openrun", "N"),
            )
        )
    return result


# ── 공연상세 파서 ───────────────────────────────────────────────────────────────

def parse_performance_detail(xml_bytes: bytes) -> RawPerformanceDetail | None:
    """
    공연상세 API(pblprfr/{mt20id}) 응답 파싱.

    응답 예시::

        <dbs>
          <db>
            <mt20id>PF123456</mt20id>
            <prfnm>레미제라블</prfnm>
            ...
            <styurls>
              <styurl>http://.../img1.jpg</styurl>
              <styurl>http://.../img2.jpg</styurl>
            </styurls>
            <relates>
              <relate>
                <relatenm>인터파크</relatenm>
                <relateurl>http://ticket.interpark.com/...</relateurl>
              </relate>
            </relates>
          </db>
        </dbs>
    """
    root = _safe_root(xml_bytes)
    if root is None:
        return None

    db = root.find("db")
    if db is None:
        logger.warning("[KOPIS Parser] 공연상세: <db> 요소 없음")
        return None

    # 소개 이미지 (다중)
    styurls_node = db.find("styurls")
    styurls: list[str] = []
    if styurls_node is not None:
        styurls = [
            node.text.strip()
            for node in styurls_node.findall("styurl")
            if node.text and node.text.strip()
        ]

    # 예매처 (다중)
    relates_node = db.find("relates")
    relates: list[dict] = []
    if relates_node is not None:
        for relate in relates_node.findall("relate"):
            name = _text(relate, "relatenm")
            url = _text(relate, "relateurl")
            if name and url:
                relates.append({"site_name": name, "url": url})

    return RawPerformanceDetail(
        mt20id=_text(db, "mt20id"),
        prfnm=_text(db, "prfnm"),
        prfpdfrom=_text(db, "prfpdfrom"),
        prfpdto=_text(db, "prfpdto"),
        fcltynm=_text(db, "fcltynm"),
        mt10id=_text(db, "mt10id"),
        prfcast=_text(db, "prfcast"),
        prfcrew=_text(db, "prfcrew"),
        prfruntime=_text(db, "prfruntime"),
        prfage=_text(db, "prfage"),
        sty=_text(db, "sty"),
        pcseguidance=_text(db, "pcseguidance"),
        genrenm=_text(db, "genrenm"),
        prfstate=_text(db, "prfstate"),
        poster=_text(db, "poster"),
        area=_text(db, "area"),
        dtguidance=_text(db, "dtguidance"),
        mt13id=_text(db, "mt13id"),
        frstregdt=_text(db, "frstregdt"),
        entrpsnm=_text(db, "entrpsnm"),
        entrpsnmP=_text(db, "entrpsnmP"),
        entrpsnmA=_text(db, "entrpsnmA"),
        entrpsnmH=_text(db, "entrpsnmH"),
        entrpsnmS=_text(db, "entrpsnmS"),
        openrun=_text(db, "openrun"),
        visit=_text(db, "visit"),
        child=_text(db, "child"),
        daehakro=_text(db, "daehakro"),
        festival=_text(db, "festival"),
        musicallicense=_text(db, "musicallicense"),
        musicalcreate=_text(db, "musicalcreate"),
        updatedate=_text(db, "updatedate"),
        styurls=styurls,
        relates=relates,
    )


# ── 공연시설 목록 파서 ─────────────────────────────────────────────────────────

def parse_venue_list(xml_bytes: bytes) -> list[str]:
    """공연시설목록 API(prfplc)에서 mt10id 목록만 추출."""
    root = _safe_root(xml_bytes)
    if root is None:
        return []
    return [
        _text(db, "mt10id")
        for db in root.findall("db")
        if _text(db, "mt10id")
    ]


# ── 공연시설 상세 파서 ─────────────────────────────────────────────────────────

def parse_venue_detail(xml_bytes: bytes) -> RawVenueDetail | None:
    """
    공연시설상세 API(prfplc/{mt10id}) 응답 파싱.

    응답 예시::

        <dbs>
          <db>
            <mt10id>FC001234</mt10id>
            <fcltynm>블루스퀘어</fcltynm>
            <sidonm>서울특별시</sidonm>
            <gugunnm>용산구</gugunnm>
            <adres>서울특별시 용산구 이태원로 294</adres>
            <la>37.5340</la>
            <lo>126.9925</lo>
            <seatscale>1766</seatscale>
          </db>
        </dbs>
    """
    root = _safe_root(xml_bytes)
    if root is None:
        return None

    db = root.find("db")
    if db is None:
        logger.warning("[KOPIS Parser] 공연시설상세: <db> 요소 없음")
        return None

    return RawVenueDetail(
        mt10id=_text(db, "mt10id"),
        fcltynm=_text(db, "fcltynm"),
        sidonm=_text(db, "sidonm"),
        gugunnm=_text(db, "gugunnm"),
        adres=_text(db, "adres"),
        la=_text(db, "la"),
        lo=_text(db, "lo"),
        seatscale=_text(db, "seatscale"),
        fcltychartr=_text(db, "fcltychartr"),
        relateurl=_text(db, "relateurl"),
        parkinglot=_text(db, "parkinglot"),
    )


# ── 날짜 변환 공개 인터페이스 ──────────────────────────────────────────────────

def to_date(raw: str) -> date | None:
    """외부에서 날짜 변환이 필요할 때 사용."""
    return _parse_kopis_date(raw)
