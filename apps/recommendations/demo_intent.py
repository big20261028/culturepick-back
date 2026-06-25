from __future__ import annotations

import re
from datetime import timedelta

from django.db.models import Q
from django.utils import timezone


DEMO_VECTOR_WEIGHT = 1.6


def _u(value: str) -> str:
    return value.encode("ascii").decode("unicode_escape")


TERMS = {
    "family": [
        r"\uac00\uc871",
        r"\uc544\uc774",
        r"\uc544\ub3d9",
        r"\uc5b4\ub9b0\uc774",
        r"\ucd08\ub4f1",
        r"\ubd80\ubaa8\ub2d8",
        r"\uc5c4\ub9c8",
        r"\uc544\ube60",
    ],
    "short_runtime": [
        r"\uc2dc\uac04\uc5c6",
        r"\uc9e7\uac8c",
        r"\uc9e7\uc740",
        r"\uac00\ubccd\uac8c",
        r"\ud1f4\uadfc\ud6c4",
        r"\ubd80\ub2f4\uc5c6\uc774",
        r"\uae08\ubc29",
    ],
    "date": [
        r"\ucee4\ud50c",
        r"\ub370\uc774\ud2b8",
        r"\uc5f0\uc778",
        r"\ub0a8\uc790\uce5c\uad6c",
        r"\uc5ec\uc790\uce5c\uad6c",
        r"\ub85c\ub9e8\ud2f1",
        r"\ub85c\ub9e8\uc2a4",
        r"\uac10\uc131",
    ],
    "friend": [r"\uce5c\uad6c", r"\ub3d9\ub8cc", r"\ubaa8\uc784"],
    "healing": [r"\ud790\ub9c1", r"\uc794\uc794", r"\uc704\ub85c", r"\uac10\ub3d9", r"\ud3b8\uc548", r"\ud734\uc2dd"],
    "exciting": [r"\uc2e0\ub098", r"\uc5d0\ub108\uc9c0", r"\ud654\ub824", r"\ucf58\uc11c\ud2b8", r"\ubc34\ub4dc"],
    "beginner": [r"\uc785\ubb38", r"\ucc98\uc74c", r"\ucd08\ubcf4", r"\ubb34\ub09c"],
    "parking": [r"\uc8fc\ucc28", r"\ucc28\ub85c", r"\uc790\ub3d9\ucc28"],
    "free": [r"\ubb34\ub8cc", r"\uacf5\uc9dc"],
    "cheap": [r"\uc800\ub834", r"\uc2f8\uac8c", r"\uc2fc", r"\uac00\uc131\ube44", r"\ubd80\ub2f4\uc5c6\ub294\uac00\uaca9"],
}

GENRE_TERMS = {
    "GGGA": [r"\ubba4\uc9c0\uceec"],
    "AAAA": [r"\uc5f0\uadf9"],
    "CCCA": [r"\ud074\ub798\uc2dd", r"\uc11c\uc591\uc74c\uc545", r"\uc624\ucf00\uc2a4\ud2b8\ub77c"],
    "CCCC": [r"\uad6d\uc545", r"\ud55c\uad6d\uc74c\uc545", r"\uc804\ud1b5\uc74c\uc545"],
    "BBBC": [r"\ubb34\uc6a9", r"\ubc1c\ub808", r"\ub304\uc2a4"],
    "CCCD": [r"\ucf58\uc11c\ud2b8", r"\ubc34\ub4dc"],
}

REGIONS = [
    r"\uc11c\uc6b8",
    r"\uacbd\uae30",
    r"\uc778\ucc9c",
    r"\ubd80\uc0b0",
    r"\ub300\uad6c",
    r"\ub300\uc804",
    r"\uad11\uc8fc",
    r"\uc6b8\uc0b0",
    r"\uc138\uc885",
    r"\uc81c\uc8fc",
]

REASONS = {
    "family_good": r"\uac00\uc871 \uad00\ub78c \ub2e8\uc11c\uac00 \uc788\uc5b4 \ud568\uaed8 \ubcf4\uae30 \uc88b\uc740 \ud6c4\ubcf4\uc785\ub2c8\ub2e4.",
    "family_age": r"\uad00\ub78c \uc5f0\ub839 \ubd80\ub2f4\uc774 \ub0ae\uc544 \uac00\uc871\uacfc \ubcf4\uae30 \uc88b\uc740 \ud6c4\ubcf4\uc785\ub2c8\ub2e4.",
    "family_weak": r"\uac00\uc871 \uad00\ub78c \uadfc\uac70\uac00 \uc57d\ud574 \uc6b0\uc120\uc21c\uc704\ub97c \ub0ae\ucdc4\uc2b5\ub2c8\ub2e4.",
    "runtime_missing": r"\ub7ec\ub2dd\ud0c0\uc784 \uc815\ubcf4\uac00 \uc5c6\uc5b4 \uc9e7\uc740 \uacf5\uc5f0 \uc870\uac74\uc740 \uc57d\ud558\uac8c\ub9cc \ubc18\uc601\ud588\uc2b5\ub2c8\ub2e4.",
    "runtime_short": r"\ub7ec\ub2dd\ud0c0\uc784\uc774 {minutes}\ubd84\uc774\ub77c \uc2dc\uac04\uc774 \ub9ce\uc9c0 \uc54a\uc744 \ub54c \ubcf4\uae30 \uc88b\uc2b5\ub2c8\ub2e4.",
    "runtime_mid": r"\ub7ec\ub2dd\ud0c0\uc784\uc774 {minutes}\ubd84\uc73c\ub85c \uc544\uc8fc \uc9e7\uc9c4 \uc54a\uc9c0\ub9cc \ubd80\ub2f4\uc740 \ud06c\uc9c0 \uc54a\uc2b5\ub2c8\ub2e4.",
    "runtime_long": r"\ub7ec\ub2dd\ud0c0\uc784\uc774 {minutes}\ubd84\uc774\ub77c \uc2dc\uac04\uc774 \uc5c6\uc744 \ub54c \uc870\uac74\uacfc\ub294 \uac70\ub9ac\uac00 \uc788\uc2b5\ub2c8\ub2e4.",
    "date": r"\uc774\uc57c\uae30\uc640 \uac10\uc0c1\uc744 \ub098\ub204\uae30 \uc88b\uc740 \uc7a5\ub974\ub77c \ub370\uc774\ud2b8 \uad00\ub78c \ud6c4\ubcf4\ub85c \uc801\ud569\ud569\ub2c8\ub2e4.",
    "healing": r"\uc794\uc794\ud55c \uac10\uc0c1\uc774\ub098 \uc704\ub85c\ub97c \uae30\ub300\ud558\uae30 \uc88b\uc740 \ub2e8\uc11c\uac00 \uc788\uc2b5\ub2c8\ub2e4.",
    "music_healing": r"\uc74c\uc545 \uc911\uc2ec \uacf5\uc5f0\uc774\ub77c \ud3b8\uc548\ud558\uac8c \uac10\uc0c1\ud558\uae30 \uc88b\uc740 \ud6c4\ubcf4\uc785\ub2c8\ub2e4.",
    "exciting": r"\ubb34\ub300 \uc5d0\ub108\uc9c0\ub098 \ubcfc\uac70\ub9ac\ub97c \uae30\ub300\ud558\uae30 \uc88b\uc740 \uc7a5\ub974\uc785\ub2c8\ub2e4.",
    "beginner": r"\uc778\uc9c0\ub3c4\ub098 \uc7a5\ub974 \uc811\uadfc\uc131\uc774 \uc788\uc5b4 \ucc98\uc74c \ubcf4\ub294 \uacf5\uc5f0\uc73c\ub85c \ubb34\ub09c\ud569\ub2c8\ub2e4.",
    "parking_good": r"\uacf5\uc5f0\uc7a5 \uc8fc\ucc28 \uac00\ub2a5 \uc815\ubcf4\uac00 \uc788\uc5b4 \uc774\ub3d9 \uc870\uac74\uc5d0 \ub9de\uc2b5\ub2c8\ub2e4.",
    "parking_weak": r"\uc8fc\ucc28 \uac00\ub2a5 \uc815\ubcf4\uac00 \ud655\uc778\ub418\uc9c0 \uc54a\uc544 \uc6b0\uc120\uc21c\uc704\ub97c \ub0ae\ucdc4\uc2b5\ub2c8\ub2e4.",
    "genre": r"\uc694\uccad\ud55c \uc7a5\ub974 \uc870\uac74\uacfc \uc815\ud655\ud788 \ub9de\ub294 \uacf5\uc5f0\uc785\ub2c8\ub2e4.",
    "free": r"\ubb34\ub8cc \uacf5\uc5f0\uc774\ub77c \uc608\uc0b0 \uc870\uac74\uc5d0 \uc815\ud655\ud788 \ub9de\uc2b5\ub2c8\ub2e4.",
    "price_all": r"\ubaa8\ub4e0 \uc88c\uc11d\uc774 {price:,}\uc6d0 \uc774\ud558\ub77c \uc608\uc0b0 \uc870\uac74\uc5d0 \uc798 \ub9de\uc2b5\ub2c8\ub2e4.",
    "price_some": r"\uc77c\ubd80 \uc88c\uc11d\uc774 {price:,}\uc6d0 \uc774\ud558\ub77c \uc608\uc0b0 \uc548\uc5d0\uc11c \uc120\ud0dd\ud560 \uc218 \uc788\uc2b5\ub2c8\ub2e4.",
    "price_over": r"\ucd5c\uc800\uac00\uac00 {price:,}\uc6d0\uc774\ub77c \uc694\uccad \uc608\uc0b0\uc744 \ub118\uc2b5\ub2c8\ub2e4.",
}


def extract_demo_intent(message: str) -> dict:
    text = _normalize_text(message)
    if not text:
        return {}

    intents = {
        "features": [],
        "price": {},
        "runtime": {},
        "schedule": {},
        "region_terms": [],
        "genre_codes": [],
    }

    if _has_any(text, TERMS["family"]):
        intents["features"].append("family")
        intents["vector_features"] = ["child"]

    if _has_any(text, TERMS["short_runtime"]):
        intents["features"].append("short_runtime")
        intents["runtime"]["max_minutes"] = 100

    if _has_any(text, TERMS["date"]):
        intents["features"].extend(["date", "romantic"])
        intents["genre_codes"].extend(["GGGA", "AAAA"])

    for feature in ("friend", "healing", "exciting", "beginner", "parking"):
        if _has_any(text, TERMS[feature]):
            intents["features"].append(feature)

    for genre_code, terms in GENRE_TERMS.items():
        if _has_any(text, terms):
            intents["genre_codes"].append(genre_code)

    if _has_any(text, TERMS["free"]):
        intents["price"] = {"is_free": True}
    else:
        max_price = _extract_price_limit(text)
        if max_price:
            intents["price"] = {"max_price": max_price}
        elif _has_any(text, TERMS["cheap"]):
            intents["price"] = {"max_price": 50000}

    if _has_any(text, [r"\uc774\ubc88\uc8fc", r"\uc8fc\ub9d0", r"\ud1a0\uc694\uc77c", r"\uc77c\uc694\uc77c", r"\uc624\ub298", r"\ub0b4\uc77c"]):
        intents["schedule"]["soon"] = True

    for region in REGIONS:
        if _u(region) in text:
            intents["region_terms"].append(_u(region))

    for key in ("features", "genre_codes", "region_terms"):
        intents[key] = _unique(intents.get(key) or [])

    return {key: value for key, value in intents.items() if value not in ({}, [], False, None)}


def build_demo_request_vector(demo_intent: dict) -> dict[str, float]:
    scores = {}
    for genre_code in demo_intent.get("genre_codes", []):
        scores[f"genre:{genre_code.lower()}"] = DEMO_VECTOR_WEIGHT

    for region in demo_intent.get("region_terms", []):
        scores[f"region:{region.lower()}"] = DEMO_VECTOR_WEIGHT * 0.8

    for feature in demo_intent.get("features", []):
        vector_feature = "child" if feature == "family" else feature
        scores[f"feature:{vector_feature}"] = DEMO_VECTOR_WEIGHT

    price = demo_intent.get("price") or {}
    if price.get("is_free"):
        scores["price:free"] = DEMO_VECTOR_WEIGHT
    elif price.get("max_price"):
        max_price = price["max_price"]
        if max_price <= 30000:
            scores["price:low"] = DEMO_VECTOR_WEIGHT
        elif max_price <= 100000:
            scores["price:low"] = DEMO_VECTOR_WEIGHT * 0.8
            scores["price:mid"] = DEMO_VECTOR_WEIGHT

    return scores


def apply_demo_queryset(queryset, demo_intent: dict, pool_size: int):
    demo_filter = build_demo_queryset_filter(demo_intent)
    if not demo_filter:
        return None

    preferred = list(queryset.filter(demo_filter)[:pool_size])
    min_required = 1 if "short_runtime" in set(demo_intent.get("features") or []) else min(8, pool_size)
    if len(preferred) >= min_required:
        return preferred
    return None


def build_demo_queryset_filter(demo_intent: dict):
    query = Q()
    has_query = False
    features = set(demo_intent.get("features") or [])

    if "family" in features:
        query |= (
            Q(is_child=True)
            | Q(age_rating__icontains=_u(r"\uc804\uccb4"))
            | Q(age_rating__icontains=_u(r"\ub9cc 7"))
            | Q(age_rating__icontains=_u(r"\ub9cc 8"))
            | Q(title__icontains=_u(r"\uac00\uc871"))
            | Q(synopsis__icontains=_u(r"\uac00\uc871"))
            | Q(synopsis__icontains=_u(r"\uc5b4\ub9b0\uc774"))
            | Q(synopsis__icontains=_u(r"\uc544\uc774"))
        )
        has_query = True

    if {"date", "romantic"} & features:
        query |= (
            Q(genre_code__in=["GGGA", "AAAA"])
            | Q(title__icontains=_u(r"\uc0ac\ub791"))
            | Q(title__icontains=_u(r"\ub85c\ub9e8"))
            | Q(synopsis__icontains=_u(r"\uc0ac\ub791"))
            | Q(synopsis__icontains=_u(r"\uc5f0\uc778"))
        )
        has_query = True

    if "exciting" in features:
        query |= Q(genre_code__in=["CCCD", "GGGA", "BBBC"]) | Q(is_festival=True)
        has_query = True

    if "parking" in features:
        query |= Q(venue__has_parking_lot=True)
        has_query = True

    if "short_runtime" in features:
        query |= Q(runtime__icontains=_u(r"\ubd84")) | Q(runtime__icontains=_u(r"\uc2dc\uac04"))
        has_query = True

    genre_codes = demo_intent.get("genre_codes") or []
    if genre_codes:
        query |= Q(genre_code__in=genre_codes)
        has_query = True

    for region in demo_intent.get("region_terms") or []:
        query |= Q(venue__sido__icontains=region) | Q(venue__gugun__icontains=region)
        has_query = True

    price = demo_intent.get("price") or {}
    if price.get("is_free"):
        query |= Q(is_free=True)
        has_query = True
    elif price.get("max_price"):
        query |= Q(is_free=True) | Q(min_price__lte=price["max_price"])
        has_query = True

    if (demo_intent.get("schedule") or {}).get("soon"):
        today = timezone.localdate()
        query |= Q(start_date__lte=today + timedelta(days=14))
        has_query = True

    return query if has_query else None


def demo_intent_score_contributions(performance, demo_intent: dict) -> list[dict]:
    contributions = []
    features = set(demo_intent.get("features") or [])
    text = _performance_text(performance)
    genre_code = (performance.genre_code or "").upper()

    if "family" in features:
        if performance.is_child or _has_any(text, [r"\uac00\uc871", r"\uc5b4\ub9b0\uc774", r"\uc544\uc774", r"\uc544\ub3d9", r"\uc804\uccb4\uad00\ub78c"]):
            contributions.append(_contribution("demo:family", 4.5, _reason("family_good")))
        elif _is_all_age(performance):
            contributions.append(_contribution("demo:family", 3.0, _reason("family_age")))
        else:
            contributions.append(_contribution("demo:family", -1.0, _reason("family_weak")))

    if "short_runtime" in features:
        minutes = _runtime_minutes(performance.runtime)
        if minutes is None:
            contributions.append(_contribution("demo:short_runtime", -1.0, _reason("runtime_missing")))
        elif minutes <= 100:
            contributions.append(_contribution("demo:short_runtime", 8.0, _reason("runtime_short").format(minutes=minutes)))
        elif minutes <= 130:
            contributions.append(_contribution("demo:short_runtime", 1.2, _reason("runtime_mid").format(minutes=minutes)))
        else:
            contributions.append(_contribution("demo:short_runtime", -4.0, _reason("runtime_long").format(minutes=minutes)))

    if {"date", "romantic"} & features:
        if _has_any(text, [r"\uc0ac\ub791", r"\uc5f0\uc778", r"\ub85c\ub9e8", r"\uac10\uc131", r"\uba5c\ub85c"]) or genre_code in {"GGGA", "AAAA"}:
            contributions.append(_contribution("demo:date", 3.0, _reason("date")))

    if "healing" in features:
        if _has_any(text, [r"\ud790\ub9c1", r"\uc704\ub85c", r"\uac10\ub3d9", r"\uc794\uc794", r"\ub530\ub73b", r"\ud3b8\uc548"]):
            contributions.append(_contribution("demo:healing", 3.0, _reason("healing")))
        elif genre_code in {"CCCA", "CCCC"}:
            contributions.append(_contribution("demo:healing", 1.4, _reason("music_healing")))

    if "exciting" in features and (genre_code in {"CCCD", "GGGA", "BBBC"} or performance.is_festival):
        contributions.append(_contribution("demo:exciting", 3.0, _reason("exciting")))

    if "beginner" in features and (performance.zzim_count >= 3 or performance.view_count >= 10 or genre_code in {"GGGA", "AAAA", "CCCA"}):
        contributions.append(_contribution("demo:beginner", 2.2, _reason("beginner")))

    if "parking" in features:
        venue = getattr(performance, "venue", None)
        if venue and venue.has_parking_lot:
            contributions.append(_contribution("demo:parking", 2.0, _reason("parking_good")))
        else:
            contributions.append(_contribution("demo:parking", -0.8, _reason("parking_weak")))

    for genre_code_intent in demo_intent.get("genre_codes", []):
        if genre_code == genre_code_intent:
            contributions.append(_contribution("demo:genre", 3.5, _reason("genre")))

    contributions.extend(_price_contributions(performance, demo_intent.get("price") or {}))
    return contributions


def _price_contributions(performance, price: dict) -> list[dict]:
    if price.get("is_free"):
        if performance.is_free:
            return [_contribution("demo:price:free", 4.0, _reason("free"))]
        return [_contribution("demo:price:free", -2.0, "Not a free performance.")]

    max_price = price.get("max_price")
    if not max_price:
        return []
    if performance.is_free:
        return [_contribution("demo:price:max", 3.5, _reason("free"))]
    if performance.max_price is not None and performance.max_price <= max_price:
        return [_contribution("demo:price:max", 3.2, _reason("price_all").format(price=max_price))]
    if performance.min_price is not None and performance.min_price <= max_price:
        return [_contribution("demo:price:max", 1.8, _reason("price_some").format(price=max_price))]
    if performance.min_price is not None:
        return [_contribution("demo:price:max", -2.2, _reason("price_over").format(price=performance.min_price))]
    return []


def _runtime_minutes(runtime: str) -> int | None:
    if not runtime:
        return None
    text = str(runtime)
    hour_match = re.search(r"(\d+)\s*" + _u(r"\uc2dc\uac04"), text)
    minute_match = re.search(r"(\d+)\s*" + _u(r"\ubd84"), text)
    total = 0
    if hour_match:
        total += int(hour_match.group(1)) * 60
    if minute_match:
        total += int(minute_match.group(1))
    if total:
        return total
    only_number = re.search(r"(\d{2,3})", text)
    return int(only_number.group(1)) if only_number else None


def _extract_price_limit(text: str) -> int | None:
    match = re.search(r"(\d+)\s*" + _u(r"\ub9cc") + r"\s*" + _u(r"\uc6d0") + r"?", text)
    if match:
        return int(match.group(1)) * 10000
    match = re.search(r"(\d{4,7})\s*" + _u(r"\uc6d0") + r"?", text)
    if match:
        return int(match.group(1))
    return None


def _is_all_age(performance) -> bool:
    return _has_any(performance.age_rating or "", [r"\uc804\uccb4", r"\ub9cc 0", r"\ub9cc 3", r"\ub9cc 5", r"\ub9cc 7", r"\ub9cc 8"])


def _performance_text(performance) -> str:
    venue = getattr(performance, "venue", None)
    return " ".join(
        str(value)
        for value in [
            performance.title,
            performance.genre,
            performance.synopsis,
            performance.age_rating,
            performance.runtime,
            performance.schedule_info,
            getattr(venue, "name", "") if venue else "",
        ]
        if value
    )


def _has_any(text: str, terms: list[str]) -> bool:
    normalized_text = _normalize_text(text)
    return any(_normalize_text(_u(term)) in normalized_text for term in terms)


def _normalize_text(message: str) -> str:
    return (message or "").strip().lower().replace(" ", "")


def _unique(values: list[str]) -> list[str]:
    result = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def _reason(key: str) -> str:
    return _u(REASONS[key])


def _contribution(key: str, score: float, reason: str) -> dict:
    return {"key": key, "score": round(score, 4), "reason": reason}
