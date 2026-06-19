from __future__ import annotations

import re


UNKNOWN_REGION_VALUES = {"", "-", "미분류", "부산부산광역시", "태국"}

SIDO_ALIASES = {
    "서울": "서울특별시",
    "서울특별시": "서울특별시",
    "부산": "부산광역시",
    "부산광역시": "부산광역시",
    "부산부산광역시": "부산광역시",
    "대구": "대구광역시",
    "대구광역시": "대구광역시",
    "인천": "인천광역시",
    "인천광역시": "인천광역시",
    "광주": "광주광역시",
    "광주광역시": "광주광역시",
    "대전": "대전광역시",
    "대전광역시": "대전광역시",
    "울산": "울산광역시",
    "울산광역시": "울산광역시",
    "세종": "세종특별자치시",
    "세종시": "세종특별자치시",
    "세종특별자치시": "세종특별자치시",
    "경기": "경기도",
    "경기도": "경기도",
    "강원": "강원특별자치도",
    "강원도": "강원특별자치도",
    "강원특별자치도": "강원특별자치도",
    "충북": "충청북도",
    "충청북도": "충청북도",
    "충남": "충청남도",
    "충청남도": "충청남도",
    "전북": "전북특별자치도",
    "전라북도": "전북특별자치도",
    "전북특별자치도": "전북특별자치도",
    "전남": "전라남도",
    "전라남도": "전라남도",
    "경북": "경상북도",
    "경상북도": "경상북도",
    "경남": "경상남도",
    "경상남도": "경상남도",
    "제주": "제주특별자치도",
    "제주도": "제주특별자치도",
    "제주특별자치도": "제주특별자치도",
}

SPECIAL_CITY_SIDOS = {
    "서울특별시",
    "부산광역시",
    "대구광역시",
    "인천광역시",
    "광주광역시",
    "대전광역시",
    "울산광역시",
}

LOCAL_SUFFIXES = ("시", "군", "구")


def is_blank_region_value(value: str | None) -> bool:
    return not value or value.strip() in UNKNOWN_REGION_VALUES


def normalize_sido(value: str | None) -> str:
    if not value:
        return ""
    normalized = value.strip()
    return SIDO_ALIASES.get(normalized, normalized)


def normalize_gugun(value: str | None) -> str:
    if not value:
        return ""
    normalized = value.strip()
    if normalized in {"-", "미분류"}:
        return ""
    return normalized if normalized.endswith(LOCAL_SUFFIXES) else ""


def parse_sido_gugun(address: str) -> tuple[str, str]:
    """Parse Korean address text into a broad sido and first city/county/district.

    For multi-level cities such as "경기도 성남시 분당구", the project stores
    "성남시" as gugun because current filters operate on broad city/county/district
    values and still search the full address for lower-level districts.
    """
    if not address or not address.strip() or address.strip() == "-":
        return "", ""

    parts = re.split(r"\s+", address.strip())
    if not parts:
        return "", ""

    sido = normalize_sido(parts[0])
    if not sido:
        return "", ""

    if sido == "세종특별자치시":
        return sido, ""

    gugun = ""
    for token in parts[1:]:
        candidate = normalize_gugun(token)
        if candidate:
            gugun = candidate
            break

    return sido, gugun


def resolve_sido_gugun(
    *,
    raw_sido: str | None = "",
    raw_gugun: str | None = "",
    address: str | None = "",
) -> tuple[str, str]:
    parsed_sido, parsed_gugun = parse_sido_gugun(address or "")
    sido = normalize_sido(raw_sido) or parsed_sido
    gugun = normalize_gugun(raw_gugun) or parsed_gugun

    if sido == "세종특별자치시":
        gugun = ""

    return sido, gugun
