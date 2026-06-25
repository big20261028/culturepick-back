from __future__ import annotations

import re
from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from math import log1p

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from apps.logs.models import SearchLog, ViewLog
from apps.performances.models import Performance, UsersPerformanceAction

from .models import (
    PerformanceVector,
    RecommendationFeedback,
    RecommendationItem,
    RecommendationSession,
    TrainingExampleCandidate,
    UserPreferenceProfile,
)
from .openai_client import (
    OpenAIRecommendationError,
    get_recommendation_provider_name,
    request_openai_recommendations,
)
from .demo_intent import (
    apply_demo_queryset,
    build_demo_request_vector,
    demo_intent_score_contributions,
    extract_demo_intent,
)


PROMPT_VERSION = "recommendation-v1"
PROFILE_VERSION = 1
PERFORMANCE_VECTOR_VERSION = 1

ACTION_WEIGHTS = {
    UsersPerformanceAction.ActionType.INTEREST: 3.0,
    UsersPerformanceAction.ActionType.WATCHLIST: 2.5,
}
VIEW_WEIGHT = 0.8
SEARCH_FILTER_WEIGHT = 0.7
SEARCH_KEYWORD_WEIGHT = 0.25
REQUEST_TEXT_WEIGHT = 1.35

FEEDBACK_SCORE_WEIGHTS = {
    RecommendationFeedback.FeedbackType.CLICK: 1,
    RecommendationFeedback.FeedbackType.INTEREST: 3,
    RecommendationFeedback.FeedbackType.WATCHLIST: 5,
    RecommendationFeedback.FeedbackType.BOOKING_LINK: 8,
    RecommendationFeedback.FeedbackType.THUMBS_UP: 4,
    RecommendationFeedback.FeedbackType.THUMBS_DOWN: -6,
    RecommendationFeedback.FeedbackType.REGENERATE: -3,
    RecommendationFeedback.FeedbackType.REASON_NOT_HELPFUL: -6,
    RecommendationFeedback.FeedbackType.NOT_MY_TASTE: -4,
    RecommendationFeedback.FeedbackType.ALREADY_SEEN: -2,
}
POSITIVE_FEEDBACK_TYPES = {
    RecommendationFeedback.FeedbackType.CLICK,
    RecommendationFeedback.FeedbackType.INTEREST,
    RecommendationFeedback.FeedbackType.WATCHLIST,
    RecommendationFeedback.FeedbackType.BOOKING_LINK,
    RecommendationFeedback.FeedbackType.THUMBS_UP,
}
BLOCKING_NEGATIVE_TYPES = {
    RecommendationFeedback.FeedbackType.THUMBS_DOWN,
    RecommendationFeedback.FeedbackType.REASON_NOT_HELPFUL,
}

DIMENSION_WEIGHTS = {
    "genre": 5.0,
    "region": 2.5,
    "price": 1.5,
    "feature": 1.25,
    "keyword": 0.35,
}

GENRE_ALIASES = {
    "AAAA": ["play"],
    "GGGA": ["musical"],
    "CCCA": ["classic"],
    "CCCC": ["koreanmusic", "korean_music"],
    "CCCD": ["concert"],
    "BBBC": ["dance", "dancing"],
    "EEEA": ["circus", "magic"],
    "EEEB": ["complex"],
}

REQUEST_GENRE_TERMS = {
    "AAAA": ["연극", "극", "드라마", "play", "drama"],
    "GGGA": ["뮤지컬", "musical"],
    "CCCA": ["클래식", "서양음악", "오케스트라", "classic", "orchestra"],
    "CCCC": ["국악", "한국음악", "전통음악", "korean music", "koreanmusic"],
    "CCCD": ["콘서트", "대중음악", "공연", "concert", "band"],
    "BBBC": ["무용", "춤", "발레", "댄스", "dance", "ballet"],
    "EEEA": ["서커스", "마술", "magic", "circus"],
    "EEEB": ["복합", "복합장르", "complex"],
}

AI_RECOMMENDATION_PROVIDERS = {"openai", "gms"}

REQUEST_REGION_TERMS = {
    "서울": ["서울", "seoul"],
    "경기": ["경기", "경기도", "gyeonggi"],
    "인천": ["인천", "incheon"],
    "부산": ["부산", "busan"],
    "대구": ["대구", "daegu"],
    "대전": ["대전", "daejeon"],
    "광주": ["광주", "gwangju"],
    "울산": ["울산", "ulsan"],
    "세종": ["세종", "sejong"],
    "강원": ["강원", "강원도", "gangwon"],
    "충북": ["충북", "충청북도", "chungbuk"],
    "충남": ["충남", "충청남도", "chungnam"],
    "전북": ["전북", "전라북도", "jeonbuk"],
    "전남": ["전남", "전라남도", "jeonnam"],
    "경북": ["경북", "경상북도", "gyeongbuk"],
    "경남": ["경남", "경상남도", "gyeongnam"],
    "제주": ["제주", "제주도", "jeju"],
}

REQUEST_PRICE_TERMS = {
    "free": ["무료", "공짜", "free"],
    "low": ["저렴", "싼", "3만원", "30000", "low"],
    "mid": ["10만원", "100000", "적당한", "보통", "mid"],
    "high": ["프리미엄", "비싼", "vip", "high"],
}

REQUEST_FEATURE_TERMS = {
    "child": ["아이", "아동", "가족", "family", "kid", "children"],
    "festival": ["축제", "페스티벌", "festival"],
    "openrun": ["오픈런", "openrun", "open run"],
}

REQUEST_INTENT_TERMS = {
    "family": ["가족", "아이", "아이와", "어린이", "초등", "family", "kid", "children"],
    "date": ["데이트", "커플", "연인", "둘이", "여자친구", "남자친구", "date", "couple"],
    "romantic": ["로맨틱", "낭만", "사랑", "연애", "감성", "멜로", "romantic"],
    "healing": ["힐링", "잔잔", "따뜻", "감동", "위로", "편안", "여유", "healing"],
    "light": ["가볍", "심심", "부담없이", "기분전환", "웃긴", "유쾌", "재밌", "comedy"],
    "exciting": ["신나", "화려", "강렬", "에너지", "댄스", "밴드", "콘서트", "exciting"],
    "beginner": ["입문", "처음", "초보", "쉽게", "대중적", "무난"],
    "parent": ["부모님", "어머니", "아버지", "어르신", "중장년"],
    "solo": ["혼자", "혼공", "나홀로", "solo"],
    "friend": ["친구", "동료", "모임", "friend"],
    "parking": ["주차", "차로", "자동차", "parking"],
    "short_runtime": ["짧은", "짧게", "퇴근 후", "평일 저녁", "가볍게"],
    "weekend": ["주말", "토요일", "일요일", "토", "일", "weekend"],
    "afternoon": ["오후", "낮", "점심", "afternoon"],
    "evening": ["저녁", "밤", "퇴근", "evening", "night"],
    "accessibility": ["장애", "장애인", "휠체어", "접근성", "배리어프리", "barrier free", "barrier-free", "accessible"],
    "hearing_accessibility": ["청각장애", "청각 장애", "자막", "수어", "수화", "문자통역", "hearing"],
    "visual_accessibility": ["시각장애", "시각 장애", "화면해설", "음성해설", "audio description", "visual"],
}

REQUEST_INTENT_VECTOR_FEATURES = {
    "family": "child",
}

REQUEST_EXCLUDE_PREVIOUS_TERMS = ["다른", "말고", "빼고", "제외", "이전", "아까", "방금", "다시", "재추천"]

PRICE_UNDER_TERMS = ("이하", "미만", "아래", "안쪽", "내", "까지", "보다 싼", "보다 저렴")
PRICE_OVER_TERMS = ("이상", "초과", "넘는", "넘게", "부터")


@dataclass(frozen=True)
class Candidate:
    performance: Performance
    score: float
    reasons: list[str]
    contributions: list[dict]


def get_or_build_user_profile(user) -> UserPreferenceProfile | None:
    if not user or not user.is_authenticated:
        return None

    profile, _ = UserPreferenceProfile.objects.get_or_create(user=user)
    if not profile.is_stale and profile.vector_data and profile.version == PROFILE_VERSION:
        return profile

    vector, source_summary = build_user_vector(user)
    profile.vector_data = vector
    profile.source_summary = source_summary
    profile.last_built_at = timezone.now()
    profile.is_stale = False
    profile.version = PROFILE_VERSION
    profile.save(update_fields=[
        "vector_data",
        "source_summary",
        "last_built_at",
        "is_stale",
        "version",
        "updated_at",
    ])
    return profile


def build_user_vector(user) -> tuple[dict[str, float], dict]:
    scores = defaultdict(float)
    source_summary = {
        "actions": 0,
        "views": 0,
        "searches": 0,
        "top_signals": [],
    }

    actions = (
        UsersPerformanceAction.objects.filter(user=user)
        .select_related("performance__venue")
        .order_by("-created_at")[:100]
    )
    for action in actions:
        weight = ACTION_WEIGHTS.get(action.action_type, 1.0)
        _add_performance_preferences(scores, action.performance, weight)
        source_summary["actions"] += 1

    recent_cutoff = timezone.now() - timedelta(days=60)
    view_logs = ViewLog.objects.filter(user=user, created_at__gte=recent_cutoff).order_by("-created_at")[:80]
    viewed_ids = [log.performance_id for log in view_logs if log.performance_id]
    performances_by_id = {
        perf.performance_id: perf
        for perf in Performance.objects.filter(performance_id__in=viewed_ids).select_related("venue")
    }
    for log in view_logs:
        performance = performances_by_id.get(log.performance_id)
        if not performance:
            continue
        _add_performance_preferences(scores, performance, VIEW_WEIGHT)
        source_summary["views"] += 1

    search_logs = SearchLog.objects.filter(user=user, created_at__gte=recent_cutoff).order_by("-created_at")[:50]
    for log in search_logs:
        _add_search_preferences(scores, log)
        source_summary["searches"] += 1

    normalized = _normalize_scores(scores)
    source_summary["top_signals"] = [
        {"key": key, "weight": value}
        for key, value in sorted(normalized.items(), key=lambda item: item[1], reverse=True)[:10]
    ]
    return normalized, source_summary


def _add_performance_preferences(scores, performance: Performance, weight: float):
    for key in build_performance_vector_data(performance).keys():
        if key.startswith(("genre:", "region:", "price:", "feature:")):
            scores[key] += weight


def _add_search_preferences(scores, log: SearchLog):
    for genre in _split_csv(log.filter_genre):
        scores[f"genre:{_normalize_token(genre)}"] += SEARCH_FILTER_WEIGHT
    for region in _split_csv(log.filter_region):
        scores[f"region:{_normalize_token(region)}"] += SEARCH_FILTER_WEIGHT
    for keyword in _split_csv(log.keyword.replace(" ", ",")):
        scores[f"keyword:{_normalize_token(keyword)}"] += SEARCH_KEYWORD_WEIGHT


def _normalize_scores(scores) -> dict[str, float]:
    if not scores:
        return {}
    max_score = max(scores.values()) or 1
    return {
        key: round(min(value / max_score, 1.0), 4)
        for key, value in scores.items()
        if value > 0
    }


def _merge_into_scores(target: dict[str, float], extra: dict[str, float]):
    for key, value in (extra or {}).items():
        target[key] = round(target.get(key, 0) + value, 4)


def _unique_preserve_order(values: list[str]) -> list[str]:
    result = []
    for value in values:
        if value not in result:
            result.append(value)
    return result


def _demo_intent_enabled() -> bool:
    return bool(getattr(settings, "AI_RECOMMENDATION_DEMO_INTENT_ENABLED", True))


def get_or_build_performance_vector(performance: Performance) -> PerformanceVector:
    vector, _ = PerformanceVector.objects.get_or_create(performance=performance)
    if _performance_vector_is_current(vector, performance):
        return vector

    vector.vector_data = build_performance_vector_data(performance)
    vector.source_summary = build_performance_source_summary(performance)
    vector.version = PERFORMANCE_VECTOR_VERSION
    vector.save(update_fields=["vector_data", "source_summary", "version", "updated_at"])
    return vector


def _performance_vector_is_current(vector: PerformanceVector, performance: Performance) -> bool:
    if not vector.vector_data or vector.version != PERFORMANCE_VECTOR_VERSION:
        return False
    synced_at = getattr(performance, "synced_at", None)
    if synced_at and vector.updated_at and synced_at > vector.updated_at:
        return False
    return True


def mark_user_recommendation_profile_stale(user):
    if not user or not getattr(user, "is_authenticated", False):
        return
    UserPreferenceProfile.objects.filter(user=user).update(is_stale=True)


def invalidate_performance_vector(performance):
    if not performance:
        return
    PerformanceVector.objects.filter(performance=performance).delete()


def build_performance_vector_data(performance: Performance) -> dict[str, float]:
    vector = {}

    genre_code = _normalize_token(performance.genre_code)
    if genre_code:
        vector[f"genre:{genre_code}"] = 1.0
        for alias in GENRE_ALIASES.get(genre_code.upper(), []):
            vector[f"genre:{alias}"] = 1.0

    genre_name = _normalize_token(performance.genre)
    if genre_name:
        vector[f"genre:{genre_name}"] = 1.0

    venue = getattr(performance, "venue", None)
    if venue:
        for value in (venue.sido, venue.gugun):
            token = _normalize_token(value)
            if token:
                vector[f"region:{token}"] = 1.0

    vector[f"price:{_price_bucket(performance)}"] = 1.0

    if performance.is_child:
        vector["feature:child"] = 1.0
    if performance.is_festival:
        vector["feature:festival"] = 1.0
    if performance.openrun:
        vector["feature:openrun"] = 1.0

    for token in _text_tokens(performance.title, limit=6):
        vector[f"keyword:{token}"] = 0.5
    return vector


def build_performance_source_summary(performance: Performance) -> dict:
    venue = getattr(performance, "venue", None)
    return {
        "performance_id": performance.performance_id,
        "title": performance.title,
        "genre": performance.genre,
        "genre_code": performance.genre_code,
        "region": getattr(venue, "sido", "") if venue else "",
        "price_bucket": _price_bucket(performance),
        "features": [
            name
            for name, enabled in (
                ("child", performance.is_child),
                ("festival", performance.is_festival),
                ("openrun", performance.openrun),
            )
            if enabled
        ],
    }


def get_recommendation_candidates(
    user=None,
    message="",
    limit=30,
    pool_size=250,
    exclude_performance_ids=None,
) -> tuple[dict, list[Candidate]]:
    profile = get_or_build_user_profile(user)
    user_vector = profile.vector_data if profile else {}
    request_intent = extract_request_intent(message)
    request_vector = build_request_vector(message)
    if _demo_intent_enabled():
        demo_intent = extract_demo_intent(message)
        if demo_intent:
            request_intent["demo"] = demo_intent
            request_intent["features"] = _unique_preserve_order(
                (request_intent.get("features") or []) + (demo_intent.get("features") or [])
            )
            _merge_into_scores(request_vector, build_demo_request_vector(demo_intent))
    combined_vector = _merge_preference_vectors(user_vector, request_vector)
    profile_snapshot = {
        "vector_data": combined_vector,
        "user_vector_data": user_vector,
        "request_vector_data": request_vector,
        "request_intent": request_intent,
        "source_summary": profile.source_summary if profile else {},
        "is_personalized": bool(user_vector),
        "has_request_signal": bool(request_vector),
    }

    queryset = _candidate_queryset(
        user,
        combined_vector,
        pool_size,
        exclude_performance_ids=exclude_performance_ids,
        request_intent=request_intent,
    )
    candidates = [_score_candidate(performance, combined_vector, request_intent) for performance in queryset]
    candidates.sort(key=lambda candidate: candidate.score, reverse=True)
    profile_snapshot["constraint_notes"] = _constraint_notes(candidates, request_intent)
    return profile_snapshot, candidates[:limit]


def build_request_vector(message: str) -> dict[str, float]:
    scores = defaultdict(float)
    if not message:
        return {}

    for genre_code, terms in REQUEST_GENRE_TERMS.items():
        if _contains_any(message, terms):
            if genre_code == "CCCD" and not _contains_any(
                message,
                ["콘서트", "대중음악", "밴드", "재즈", "락", "록", "concert", "band", "jazz"],
            ):
                continue
            normalized_code = _normalize_token(genre_code)
            scores[f"genre:{normalized_code}"] += 1.0
            for alias in GENRE_ALIASES.get(genre_code, []):
                scores[f"genre:{_normalize_token(alias)}"] += 0.85

    for region, terms in REQUEST_REGION_TERMS.items():
        if _contains_any(message, terms):
            scores[f"region:{_normalize_token(region)}"] += 1.0
            for term in terms:
                scores[f"region:{_normalize_token(term)}"] += 0.8

    for bucket, terms in REQUEST_PRICE_TERMS.items():
        if _contains_any(message, terms):
            scores[f"price:{bucket}"] += 1.0

    for feature, terms in REQUEST_FEATURE_TERMS.items():
        if _contains_any(message, terms):
            scores[f"feature:{feature}"] += 1.0

    request_intent = extract_request_intent(message)
    for feature in request_intent.get("features", []):
        vector_feature = REQUEST_INTENT_VECTOR_FEATURES.get(feature, feature)
        scores[f"feature:{vector_feature}"] += 0.85

    price_intent = request_intent.get("price") or {}
    if price_intent.get("is_free"):
        scores["price:free"] += 1.2
    elif price_intent.get("max_price"):
        max_price = price_intent["max_price"]
        if max_price <= 30000:
            scores["price:low"] += 1.0
        elif max_price <= 100000:
            scores["price:mid"] += 1.0
            scores["price:low"] += 0.65
        else:
            scores["price:high"] += 0.5
            scores["price:mid"] += 0.4
    elif price_intent.get("min_price"):
        scores["price:high"] += 0.7

    for token in _text_tokens(message, limit=8):
        scores[f"keyword:{token}"] += 0.3

    return _normalize_scores(scores)


def extract_request_intent(message: str) -> dict:
    text = (message or "").strip()
    if not text:
        return {}

    features = [
        name
        for name, terms in REQUEST_INTENT_TERMS.items()
        if _contains_any(text, terms)
    ]
    price_intent = _extract_price_intent(text)
    runtime_intent = _extract_runtime_intent(text)
    schedule_intent = _extract_schedule_intent(text)
    accessibility_intent = _extract_accessibility_intent(text)
    return {
        "features": features,
        "price": price_intent,
        "runtime": runtime_intent,
        "schedule": schedule_intent,
        "accessibility": accessibility_intent,
        "raw_terms": _text_tokens(text, limit=12),
    }


def _candidate_queryset(user, user_vector: dict[str, float], pool_size: int, exclude_performance_ids=None, request_intent=None):
    today = timezone.localdate()
    queryset = (
        Performance.objects.select_related("venue")
        .prefetch_related("price_options")
        .filter(Q(end_date__isnull=True) | Q(end_date__gte=today))
        .order_by("-zzim_count", "-view_count", "start_date", "title")
    )

    if user and user.is_authenticated:
        selected_ids = UsersPerformanceAction.objects.filter(user=user).values_list("performance_id", flat=True)
        queryset = queryset.exclude(performance_id__in=selected_ids)

    if exclude_performance_ids:
        queryset = queryset.exclude(performance_id__in=exclude_performance_ids)

    if _demo_intent_enabled():
        demo_preferred = apply_demo_queryset(queryset, (request_intent or {}).get("demo") or {}, pool_size)
        if demo_preferred is not None:
            return demo_preferred

    preference_filter = _build_preference_filter(user_vector)
    if preference_filter:
        preferred = queryset.filter(preference_filter)[:pool_size]
        if len(preferred) >= min(30, pool_size):
            return preferred

    return queryset[:pool_size]


def _build_preference_filter(user_vector):
    top_keys = [key for key, _ in sorted(user_vector.items(), key=lambda item: item[1], reverse=True)[:12]]
    query = Q()
    has_query = False
    for key in top_keys:
        dimension, value = _split_vector_key(key)
        if dimension == "genre":
            query |= Q(genre_code__iexact=value.upper()) | Q(genre__icontains=value)
            has_query = True
        elif dimension == "region":
            query |= Q(venue__sido__icontains=value) | Q(venue__gugun__icontains=value)
            has_query = True
    return query if has_query else None


def _merge_preference_vectors(user_vector: dict[str, float], request_vector: dict[str, float]) -> dict[str, float]:
    combined = defaultdict(float)
    for key, value in (user_vector or {}).items():
        combined[key] += value
    for key, value in (request_vector or {}).items():
        combined[key] += value * REQUEST_TEXT_WEIGHT
    return {
        key: round(value, 4)
        for key, value in combined.items()
        if value > 0
    }


def _score_candidate(performance: Performance, user_vector: dict[str, float], request_intent=None) -> Candidate:
    performance_vector = get_or_build_performance_vector(performance).vector_data
    contributions = []
    score = 0.0

    for key, user_value in user_vector.items():
        performance_value = performance_vector.get(key)
        if not performance_value:
            continue
        dimension, _ = _split_vector_key(key)
        contribution = user_value * performance_value * DIMENSION_WEIGHTS.get(dimension, 1.0)
        if contribution <= 0:
            continue
        score += contribution
        contributions.append({
            "key": key,
            "score": round(contribution, 4),
            "reason": _reason_for_key(key),
        })

    for intent_contribution in _intent_score_contributions(performance, request_intent or {}):
        score += intent_contribution["score"]
        contributions.append(intent_contribution)

    if _demo_intent_enabled():
        for intent_contribution in demo_intent_score_contributions(
            performance,
            (request_intent or {}).get("demo") or {},
        ):
            score += intent_contribution["score"]
            contributions.append(intent_contribution)

    score += _availability_bonus(performance)
    score += _popularity_bonus(performance)
    contributions.sort(key=lambda item: item["score"], reverse=True)
    reasons = [item["reason"] for item in contributions[:3]]
    if not reasons:
        reasons = _fallback_reasons(performance)

    return Candidate(
        performance=performance,
        score=round(score, 4),
        reasons=reasons,
        contributions=contributions[:5],
    )


def create_ai_recommendation(user, message="", limit=5, candidate_limit=12, previous_session_id=None) -> RecommendationSession:
    try:
        provider = get_recommendation_provider_name()
    except OpenAIRecommendationError:
        provider = "openai"

    conversation_context = _previous_recommendation_context(user, previous_session_id)
    exclude_ids = _previous_recommendation_ids(conversation_context) if _should_exclude_previous(message) else []
    profile_snapshot, candidates = get_recommendation_candidates(
        user=user,
        message=message,
        limit=max(candidate_limit, limit),
        exclude_performance_ids=exclude_ids,
    )
    if conversation_context:
        profile_snapshot["conversation_context"] = conversation_context
    candidate_snapshot = [_candidate_payload(candidate) for candidate in candidates]

    session = RecommendationSession.objects.create(
        user=user if user and user.is_authenticated else None,
        request_text=message or "",
        provider=provider,
        model_name="",
        prompt_version=PROMPT_VERSION,
        user_profile_snapshot=profile_snapshot,
        candidate_snapshot=candidate_snapshot,
    )

    try:
        parsed, raw, model_name = request_openai_recommendations(
            user_request=message or "",
            profile_snapshot=profile_snapshot,
            candidates=candidate_snapshot,
            limit=limit,
        )
        session.model_name = model_name
        session.raw_response = raw
        valid_items = _validate_openai_items(parsed, candidates, limit)
        if valid_items:
            session.parsed_response = parsed
            session.validation_status = RecommendationSession.ValidationStatus.PASSED
            session.fallback_used = False
            session.save(update_fields=[
                "model_name",
                "raw_response",
                "parsed_response",
                "validation_status",
                "fallback_used",
            ])
            _save_recommendation_items(session, valid_items, RecommendationItem.Source.OPENAI)
            return session
        session.parsed_response = parsed
        session.validation_status = RecommendationSession.ValidationStatus.FAILED
    except OpenAIRecommendationError as exc:
        session.raw_response = {"error": str(exc)}
        session.validation_status = RecommendationSession.ValidationStatus.FAILED

    fallback_items = _fallback_items(candidates, limit, profile_snapshot)
    session.provider = "rule_based"
    session.fallback_used = True
    session.parsed_response = {
        "summary": _fallback_summary(profile_snapshot),
        "recommendations": [
            {
                "performance_id": item["performance"].performance_id,
                "rank": item["rank"],
                "reason": item["reason"],
            }
            for item in fallback_items
        ],
    }
    session.validation_status = RecommendationSession.ValidationStatus.FALLBACK
    session.save(update_fields=[
        "provider",
        "raw_response",
        "parsed_response",
        "validation_status",
        "fallback_used",
    ])
    _save_recommendation_items(session, fallback_items, RecommendationItem.Source.FALLBACK)
    return session


def record_feedback_and_update_quality(*, session, user=None, performance=None, feedback_type="", metadata=None):
    feedback = RecommendationFeedback.objects.create(
        session=session,
        user=user if user and user.is_authenticated else None,
        performance=performance,
        feedback_type=feedback_type,
        metadata=metadata or {},
    )
    refresh_session_quality(session)
    return feedback


def refresh_session_quality(session: RecommendationSession) -> RecommendationSession:
    feedback_types = list(session.feedback.values_list("feedback_type", flat=True))
    quality_score = sum(FEEDBACK_SCORE_WEIGHTS.get(feedback_type, 0) for feedback_type in feedback_types)
    session.quality_score = quality_score
    session.save(update_fields=["quality_score"])
    sync_training_candidate(session, feedback_types)
    return session


def sync_training_candidate(session: RecommendationSession, feedback_types=None):
    feedback_types = feedback_types if feedback_types is not None else list(session.feedback.values_list("feedback_type", flat=True))
    if (
        not _is_ai_recommendation_provider(session.provider)
        or session.fallback_used
        or session.validation_status != RecommendationSession.ValidationStatus.PASSED
    ):
        TrainingExampleCandidate.objects.filter(source_session=session).delete()
        return None

    status, approved, rejection_reasons = classify_training_candidate(session, feedback_types)

    if status == TrainingExampleCandidate.Status.REJECTED and not _has_training_payload(session):
        return None

    input_payload = build_training_input_payload(session)
    output_payload = build_training_output_payload(session)
    candidate, _ = TrainingExampleCandidate.objects.update_or_create(
        source_session=session,
        defaults={
            "status": status,
            "training_task": TrainingExampleCandidate.TrainingTask.RECOMMENDATION_REASONING,
            "input_payload": input_payload,
            "output_payload": output_payload,
            "chosen_output": output_payload if approved else {},
            "rejected_output": output_payload if status == TrainingExampleCandidate.Status.REJECTED else {},
            "quality_score": session.quality_score or 0,
            "rejection_reasons": rejection_reasons,
            "approved_for_training": approved,
        },
    )
    return candidate


def classify_training_candidate(session: RecommendationSession, feedback_types: list[str]):
    rejection_reasons = []
    has_positive_feedback = any(feedback_type in POSITIVE_FEEDBACK_TYPES for feedback_type in feedback_types)
    has_blocking_negative = any(feedback_type in BLOCKING_NEGATIVE_TYPES for feedback_type in feedback_types)

    if not _is_ai_recommendation_provider(session.provider):
        rejection_reasons.append("provider_not_ai")
    if session.fallback_used:
        rejection_reasons.append("fallback_used")
    if session.validation_status != RecommendationSession.ValidationStatus.PASSED:
        rejection_reasons.append("validation_not_passed")
    if not session.parsed_response.get("recommendations"):
        rejection_reasons.append("missing_recommendations")
    if not session.candidate_snapshot:
        rejection_reasons.append("missing_candidates")
    if has_blocking_negative:
        rejection_reasons.append("blocking_negative_feedback")

    quality_score = session.quality_score or 0
    if rejection_reasons or quality_score <= 0:
        if quality_score <= 0:
            rejection_reasons.append("non_positive_quality_score")
        return TrainingExampleCandidate.Status.REJECTED, False, rejection_reasons
    if quality_score >= 8 and has_positive_feedback:
        return TrainingExampleCandidate.Status.AUTO_APPROVED, True, []
    if 3 <= quality_score < 8:
        return TrainingExampleCandidate.Status.NEEDS_REVIEW, False, []
    return TrainingExampleCandidate.Status.REJECTED, False, ["quality_score_below_review_threshold"]


def build_training_input_payload(session: RecommendationSession) -> dict:
    return {
        "task": TrainingExampleCandidate.TrainingTask.RECOMMENDATION_REASONING,
        "prompt_version": session.prompt_version,
        "user_request": session.request_text,
        "user_profile": session.user_profile_snapshot,
        "candidates": session.candidate_snapshot,
    }


def build_training_output_payload(session: RecommendationSession) -> dict:
    return {
        "summary": session.parsed_response.get("summary", ""),
        "recommendations": session.parsed_response.get("recommendations", []),
    }


def _has_training_payload(session: RecommendationSession) -> bool:
    return bool(session.candidate_snapshot or session.parsed_response)


def _is_ai_recommendation_provider(provider: str) -> bool:
    return provider in AI_RECOMMENDATION_PROVIDERS


def _previous_recommendation_context(user, previous_session_id) -> dict:
    if not previous_session_id or not user or not getattr(user, "is_authenticated", False):
        return {}

    session = (
        RecommendationSession.objects.filter(pk=previous_session_id, user=user)
        .prefetch_related("items__performance")
        .first()
    )
    if not session:
        return {}

    return {
        "session_id": session.id,
        "request_text": session.request_text,
        "summary": session.parsed_response.get("summary", ""),
        "recommendations": [
            {
                "performance_id": item.performance_id,
                "title": item.performance.title,
                "rank": item.rank,
                "reason": item.reason,
            }
            for item in session.items.all()[:10]
        ],
    }


def _previous_recommendation_ids(conversation_context: dict) -> list[str]:
    return [
        item.get("performance_id")
        for item in conversation_context.get("recommendations", [])
        if item.get("performance_id")
    ]


def _should_exclude_previous(message: str) -> bool:
    return _contains_any(message or "", REQUEST_EXCLUDE_PREVIOUS_TERMS)


def _validate_openai_items(parsed: dict, candidates: list[Candidate], limit: int) -> list[dict]:
    candidate_map = {candidate.performance.performance_id: candidate for candidate in candidates}
    valid_items = []
    seen = set()
    for item in parsed.get("recommendations", []):
        performance_id = item.get("performance_id")
        reason = (item.get("reason") or "").strip()
        if not performance_id or performance_id in seen or not reason:
            continue
        candidate = candidate_map.get(performance_id)
        if not candidate:
            continue
        seen.add(performance_id)
        valid_items.append({
            "performance": candidate.performance,
            "rank": len(valid_items) + 1,
            "score": candidate.score,
            "reason": reason,
        })
        if len(valid_items) >= limit:
            break
    return valid_items


def _fallback_summary(profile_snapshot: dict) -> str:
    notes = profile_snapshot.get("constraint_notes") or []
    if notes:
        return " ".join(notes)
    return "추천 후보를 기준으로 공연을 골랐습니다."


def _fallback_items(candidates: list[Candidate], limit: int, profile_snapshot: dict | None = None) -> list[dict]:
    constraint_prefix = _fallback_constraint_prefix(profile_snapshot or {})
    return [
        {
            "performance": candidate.performance,
            "rank": index + 1,
            "score": candidate.score,
            "reason": _fallback_reason(candidate, constraint_prefix),
        }
        for index, candidate in enumerate(candidates[:limit])
    ]


def _fallback_constraint_prefix(profile_snapshot: dict) -> str:
    notes = profile_snapshot.get("constraint_notes") or []
    return " ".join(note for note in notes if note)


def _fallback_reason(candidate: Candidate, constraint_prefix: str = "") -> str:
    reason = candidate.reasons[0] if candidate.reasons else "추천 후보 점수가 높습니다."
    if constraint_prefix and constraint_prefix not in reason:
        return f"{constraint_prefix} {reason}"
    return reason


def _save_recommendation_items(session, items: list[dict], source: str):
    RecommendationItem.objects.bulk_create([
        RecommendationItem(
            session=session,
            performance=item["performance"],
            rank=item["rank"],
            score=item.get("score", 0),
            reason=item.get("reason", ""),
            source=source,
        )
        for item in items
    ])


def _extract_price_intent(message: str) -> dict:
    text = message or ""
    normalized = text.replace(",", "").replace(" ", "")
    if _contains_any(text, ["무료", "공짜", "free"]):
        return {"is_free": True, "max_price": 0, "label": "무료"}

    price_intent = {}
    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*만\s*원?\s*([가-힣\s]*)", text):
        amount = int(float(match.group(1)) * 10000)
        qualifier = (match.group(2) or "")[:8]
        _apply_price_qualifier(price_intent, amount, qualifier)

    for match in re.finditer(r"(\d{2,9})원?\s*([가-힣\s]*)", normalized):
        amount = int(match.group(1))
        if amount < 1000:
            continue
        qualifier = (match.group(2) or "")[:8]
        _apply_price_qualifier(price_intent, amount, qualifier)

    if not price_intent:
        return {}
    if "label" not in price_intent:
        if price_intent.get("max_price") is not None:
            price_intent["label"] = f"{price_intent['max_price']}원 이하"
        elif price_intent.get("min_price") is not None:
            price_intent["label"] = f"{price_intent['min_price']}원 이상"
    return price_intent


def _apply_price_qualifier(price_intent: dict, amount: int, qualifier: str):
    if any(term in qualifier for term in PRICE_OVER_TERMS):
        current = price_intent.get("min_price")
        price_intent["min_price"] = amount if current is None else max(current, amount)
        return

    current = price_intent.get("max_price")
    price_intent["max_price"] = amount if current is None else min(current, amount)


def _extract_runtime_intent(message: str) -> dict:
    text = message or ""
    runtime_intent = {}
    for match in re.finditer(r"(\d+(?:\.\d+)?)\s*시간\s*([가-힣\s]*)", text):
        minutes = int(float(match.group(1)) * 60)
        qualifier = (match.group(2) or "")[:8]
        _apply_runtime_qualifier(runtime_intent, minutes, qualifier)
    for match in re.finditer(r"(\d{2,3})\s*분\s*([가-힣\s]*)", text):
        minutes = int(match.group(1))
        qualifier = (match.group(2) or "")[:8]
        _apply_runtime_qualifier(runtime_intent, minutes, qualifier)
    if not runtime_intent and _contains_any(text, ["짧은", "짧게", "가볍게", "퇴근 후"]):
        runtime_intent["max_minutes"] = 100
        runtime_intent["label"] = "짧은 러닝타임"
    return runtime_intent


def _apply_runtime_qualifier(runtime_intent: dict, minutes: int, qualifier: str):
    if any(term in qualifier for term in PRICE_OVER_TERMS):
        current = runtime_intent.get("min_minutes")
        runtime_intent["min_minutes"] = minutes if current is None else max(current, minutes)
        return
    current = runtime_intent.get("max_minutes")
    runtime_intent["max_minutes"] = minutes if current is None else min(current, minutes)
    runtime_intent["label"] = f"{minutes}분 이하"


def _extract_schedule_intent(message: str) -> dict:
    text = message or ""
    schedule = {}
    if _contains_any(text, ["주말", "토요일", "일요일", "토", "일", "weekend"]):
        schedule["days"] = ["토", "일"]
    if _contains_any(text, ["평일", "월요일", "화요일", "수요일", "목요일", "금요일"]):
        schedule["days"] = ["월", "화", "수", "목", "금"]
    if _contains_any(text, ["오후", "낮", "점심", "afternoon"]):
        schedule["time_of_day"] = "afternoon"
    elif _contains_any(text, ["저녁", "밤", "퇴근", "evening", "night"]):
        schedule["time_of_day"] = "evening"
    elif _contains_any(text, ["오전", "아침", "morning"]):
        schedule["time_of_day"] = "morning"
    return schedule


def _extract_accessibility_intent(message: str) -> dict:
    text = message or ""
    needs = []
    if _contains_any(text, ["휠체어", "이동약자", "무장애", "접근성", "배리어프리", "barrier free", "barrier-free", "accessible"]):
        needs.append("mobility")
    if _contains_any(text, ["청각장애", "청각 장애", "자막", "수어", "수화", "문자통역", "hearing"]):
        needs.append("hearing")
    if _contains_any(text, ["시각장애", "시각 장애", "화면해설", "음성해설", "audio description", "visual"]):
        needs.append("visual")
    return {
        "needs": needs,
        "data_available": False,
    } if needs else {}


def _intent_score_contributions(performance: Performance, request_intent: dict) -> list[dict]:
    contributions = []
    price_contribution = _price_intent_contribution(performance, request_intent.get("price") or {})
    if price_contribution:
        contributions.append(price_contribution)

    runtime_contribution = _runtime_intent_contribution(performance, request_intent.get("runtime") or {})
    if runtime_contribution:
        contributions.append(runtime_contribution)

    schedule_contribution = _schedule_intent_contribution(performance, request_intent.get("schedule") or {})
    if schedule_contribution:
        contributions.append(schedule_contribution)

    for accessibility_contribution in _accessibility_intent_contributions(performance, request_intent.get("accessibility") or {}):
        contributions.append(accessibility_contribution)

    features = request_intent.get("features") or []
    for feature in features:
        contribution = _feature_intent_contribution(performance, feature)
        if contribution:
            contributions.append(contribution)
    return contributions


def _price_intent_contribution(performance: Performance, price_intent: dict) -> dict | None:
    if not price_intent:
        return None

    if price_intent.get("is_free"):
        if performance.is_free:
            return _contribution("intent:price:free", 3.0, "무료 공연 조건에 맞습니다.")
        return _contribution("intent:price:free", -2.0, "무료 조건과는 맞지 않습니다.")

    max_price = price_intent.get("max_price")
    min_price = price_intent.get("min_price")
    perf_min = performance.min_price
    perf_max = performance.max_price

    if max_price is not None:
        if performance.is_free:
            return _contribution("intent:price:max", 2.8, f"무료 공연이라 {max_price:,}원 이하 예산에 충분히 맞습니다.")
        if perf_max is not None and perf_max <= max_price:
            return _contribution("intent:price:max", 2.5, f"전 좌석 가격이 {max_price:,}원 이하 조건에 맞습니다.")
        if perf_min is not None and perf_min <= max_price:
            return _contribution("intent:price:max", 1.3, f"일부 좌석이 {max_price:,}원 이하 예산에 들어옵니다.")
        if perf_min is not None and perf_min > max_price:
            gap_score = max(0.2, 1.0 - ((perf_min - max_price) / 50000))
            if gap_score <= 0.25:
                gap_score = -1.6
            return _contribution("intent:price:max", gap_score, f"요청 예산을 넘지만 후보 중 가격이 낮은 편인지 함께 비교했습니다. 최저가는 {perf_min:,}원입니다.")
        return _contribution("intent:price:max", -0.4, "가격 정보가 부족해 예산 조건은 약하게만 반영했습니다.")

    if min_price is not None:
        if perf_max is not None and perf_max >= min_price:
            return _contribution("intent:price:min", 0.8, f"{min_price:,}원 이상 가격대의 좌석을 포함합니다.")
        return _contribution("intent:price:min", -0.4, "요청한 가격대보다 낮은 공연일 수 있습니다.")
    return None


def _runtime_intent_contribution(performance: Performance, runtime_intent: dict) -> dict | None:
    if not runtime_intent:
        return None
    minutes = _runtime_minutes(performance.runtime)
    max_minutes = runtime_intent.get("max_minutes")
    min_minutes = runtime_intent.get("min_minutes")
    if max_minutes is not None:
        if minutes is None:
            return _contribution("intent:runtime:max", -0.2, "러닝타임 정보가 없어 시간 조건은 확실히 판단하기 어렵습니다.")
        if minutes <= max_minutes:
            shorter_bonus = max((max_minutes - minutes) / max_minutes, 0)
            return _contribution("intent:runtime:max", 1.8 + shorter_bonus, f"러닝타임이 {minutes}분이라 {max_minutes}분 이하 조건에 맞습니다.")
        return _contribution("intent:runtime:max", -1.5, f"러닝타임이 {minutes}분이라 요청한 시간 조건을 넘습니다.")
    if min_minutes is not None:
        if minutes is None:
            return _contribution("intent:runtime:min", -0.2, "러닝타임 정보가 없어 시간 조건은 확실히 판단하기 어렵습니다.")
        if minutes >= min_minutes:
            return _contribution("intent:runtime:min", 0.8, f"러닝타임이 {minutes}분이라 요청한 길이 조건에 맞습니다.")
    return None


def _schedule_intent_contribution(performance: Performance, schedule_intent: dict) -> dict | None:
    if not schedule_intent:
        return None
    schedule_text = performance.schedule_info or ""
    if not schedule_text:
        return _contribution("intent:schedule", -0.2, "공연 시간 정보가 부족해 일정 조건은 확실히 판단하기 어렵습니다.")

    score = 0.0
    reasons = []
    days = schedule_intent.get("days") or []
    if days:
        if any(day in schedule_text for day in days):
            score += 1.4
            reasons.append("요청한 요일 조건과 공연 시간 정보가 맞습니다.")
        else:
            score -= 0.9
            reasons.append("공연 시간 정보에서 요청한 요일 조건은 확인되지 않습니다.")

    time_of_day = schedule_intent.get("time_of_day")
    if time_of_day:
        if _schedule_matches_time_of_day(schedule_text, time_of_day):
            score += 1.1
            reasons.append("요청한 시간대와 맞는 회차가 있습니다.")
        else:
            score -= 0.5
            reasons.append("요청한 시간대와 정확히 맞는 회차는 확인되지 않습니다.")

    if not reasons:
        return None
    return _contribution("intent:schedule", score, " ".join(reasons))


def _accessibility_intent_contributions(performance: Performance, accessibility_intent: dict) -> list[dict]:
    needs = accessibility_intent.get("needs") or []
    if not needs:
        return []

    contributions = [
        _contribution(
            "intent:accessibility:data_unavailable",
            -0.8,
            "접근성 지원 여부를 판단할 전용 데이터가 없어 조건을 완전히 확인하지 못했습니다.",
        )
    ]
    venue = getattr(performance, "venue", None)
    if venue and venue.has_parking_lot and "mobility" in needs:
        contributions.append(_contribution("intent:accessibility:mobility_hint", 0.4, "주차 가능 정보는 있어 이동 편의의 약한 참고 신호로만 반영했습니다."))
    return contributions


def _feature_intent_contribution(performance: Performance, feature: str) -> dict | None:
    text = _performance_text(performance)
    genre_code = (performance.genre_code or "").upper()

    if feature == "family":
        if performance.is_child or _contains_any(text, ["전체", "어린이", "가족", "아이", "키즈", "아동"]):
            return _contribution("intent:family", 2.4, "가족이나 아이와 함께 보기 좋은 요소가 있습니다.")
        if _is_all_age(performance):
            return _contribution("intent:family", 1.2, "관람 연령 부담이 낮아 가족 관람 후보로 볼 수 있습니다.")
        return _contribution("intent:family", -0.6, "가족 관람 조건은 뚜렷하게 확인되지 않습니다.")

    if feature in {"date", "romantic"}:
        if _contains_any(text, ["로맨", "사랑", "연애", "데이트", "감성", "낭만", "멜로"]):
            return _contribution(f"intent:{feature}", 2.0, "데이트나 커플 관람에 어울리는 감성 요소가 있습니다.")
        if genre_code in {"GGGA", "AAAA"}:
            return _contribution(f"intent:{feature}", 0.8, "뮤지컬/연극 장르라 둘이 이야기 나누기 좋은 선택지입니다.")

    if feature == "healing":
        if _contains_any(text, ["힐링", "위로", "따뜻", "감동", "잔잔", "편안", "여유"]):
            return _contribution("intent:healing", 1.8, "잔잔하거나 따뜻한 분위기를 기대할 수 있는 단서가 있습니다.")
        return _contribution("intent:healing", 0.3, "기분 전환용 후보로는 볼 수 있지만 힐링 단서는 강하지 않습니다.")

    if feature == "light":
        if _contains_any(text, ["코미디", "웃음", "유쾌", "재미", "쇼", "마술", "가볍"]):
            return _contribution("intent:light", 1.8, "부담 없이 즐기기 좋은 유쾌한 단서가 있습니다.")
        if genre_code in {"EEEA", "EEEB", "CCCD"}:
            return _contribution("intent:light", 0.9, "가볍게 기분 전환하기 좋은 장르 후보입니다.")

    if feature == "exciting":
        if genre_code in {"CCCD", "BBBC"} or performance.is_festival:
            return _contribution("intent:exciting", 1.8, "신나고 에너지 있는 공연을 찾는 요청과 잘 맞습니다.")
        if _contains_any(text, ["화려", "강렬", "댄스", "밴드", "콘서트", "축제"]):
            return _contribution("intent:exciting", 1.5, "무대 에너지나 볼거리가 기대되는 단서가 있습니다.")

    if feature == "beginner":
        if performance.zzim_count >= 5 or performance.view_count >= 20:
            return _contribution("intent:beginner", 1.0, "관심/조회 신호가 있어 입문자에게 무난한 후보입니다.")
        if genre_code in {"GGGA", "AAAA", "CCCA"}:
            return _contribution("intent:beginner", 0.7, "처음 접하기 비교적 쉬운 장르 후보입니다.")

    if feature == "parent":
        if genre_code in {"CCCA", "CCCC", "AAAA"}:
            return _contribution("intent:parent", 2.4, "부모님과 함께 보기 좋은 차분한 장르 후보입니다.")
        if _contains_any(text, ["국악", "클래식", "전통", "명작", "감동"]):
            return _contribution("intent:parent", 2.0, "부모님 관람에 어울릴 만한 소재 단서가 있습니다.")

    if feature == "parking":
        venue = getattr(performance, "venue", None)
        if venue and venue.has_parking_lot:
            return _contribution("intent:parking", 1.0, "공연장 주차 가능 정보가 있어 이동 조건에 맞습니다.")
        return _contribution("intent:parking", -0.4, "주차 가능 여부는 확인되지 않습니다.")

    if feature == "short_runtime":
        minutes = _runtime_minutes(performance.runtime)
        if minutes and minutes <= 100:
            return _contribution("intent:short_runtime", 1.0, "러닝타임이 비교적 짧아 가볍게 보기 좋습니다.")

    return None


def _contribution(key: str, score: float, reason: str) -> dict:
    return {"key": key, "score": round(score, 4), "reason": reason}


def _performance_text(performance: Performance) -> str:
    venue = getattr(performance, "venue", None)
    return " ".join(
        value
        for value in [
            performance.title,
            performance.genre,
            performance.synopsis,
            performance.age_rating,
            performance.runtime,
            performance.schedule_info,
            getattr(venue, "name", "") if venue else "",
            getattr(venue, "facility_characteristic", "") if venue else "",
        ]
        if value
    )


def _is_all_age(performance: Performance) -> bool:
    return _contains_any(performance.age_rating or "", ["전체", "만 7", "만7", "만 8", "만8", "36개월", "5세"])


def _runtime_minutes(runtime: str) -> int | None:
    if not runtime:
        return None
    match = re.search(r"(\d+)\s*분", runtime)
    if match:
        return int(match.group(1))
    match = re.search(r"(\d+)\s*시간(?:\s*(\d+)\s*분)?", runtime)
    if match:
        return int(match.group(1)) * 60 + int(match.group(2) or 0)
    return None


def _schedule_matches_time_of_day(schedule_text: str, time_of_day: str) -> bool:
    hours = [int(match) for match in re.findall(r"(\d{1,2})\s*:", schedule_text or "")]
    if not hours:
        return False
    if time_of_day == "morning":
        return any(5 <= hour < 12 for hour in hours)
    if time_of_day == "afternoon":
        return any(12 <= hour < 18 for hour in hours)
    if time_of_day == "evening":
        return any(hour >= 18 or hour < 5 for hour in hours)
    return False


def _constraint_notes(candidates: list[Candidate], request_intent: dict) -> list[str]:
    notes = []
    if not request_intent:
        return notes

    price_intent = request_intent.get("price") or {}
    max_price = price_intent.get("max_price")
    if max_price is not None and not any(_performance_satisfies_max_price(candidate.performance, max_price) for candidate in candidates):
        cheapest = _cheapest_candidate(candidates)
        if cheapest:
            performance = cheapest.performance
            cheapest_price = "무료" if performance.is_free else f"{performance.min_price:,}원"
            notes.append(
                f"요청한 {max_price:,}원 이하 조건을 정확히 만족하는 후보가 없어 최저가가 가장 낮은 공연을 우선 대체 후보로 포함했습니다. "
                f"가장 낮은 후보는 {performance.title}이며 최저가는 {cheapest_price}입니다."
            )

    runtime_intent = request_intent.get("runtime") or {}
    max_minutes = runtime_intent.get("max_minutes")
    if max_minutes is not None and not any(_performance_satisfies_max_runtime(candidate.performance, max_minutes) for candidate in candidates):
        notes.append(f"{max_minutes}분 이하 러닝타임 조건을 정확히 만족하는 후보를 찾지 못해 러닝타임 정보가 있거나 비교적 짧은 후보를 함께 검토했습니다.")

    schedule_intent = request_intent.get("schedule") or {}
    if schedule_intent and not any(_performance_satisfies_schedule(candidate.performance, schedule_intent) for candidate in candidates):
        notes.append("요청한 요일/시간대 조건과 정확히 맞는 공연 시간 정보를 찾지 못해 일정 조건은 부분 일치 후보까지 넓혀 추천했습니다.")

    accessibility_intent = request_intent.get("accessibility") or {}
    if accessibility_intent.get("needs"):
        notes.append("현재 공연/공연장 데이터에는 청각장애, 시각장애, 휠체어 접근성 지원 여부를 확정할 전용 필드가 없어 정확 필터링 대신 데이터 부족 사실을 안내해야 합니다.")

    return notes


def _performance_satisfies_max_price(performance: Performance, max_price: int) -> bool:
    if performance.is_free:
        return True
    if performance.max_price is not None and performance.max_price <= max_price:
        return True
    return performance.min_price is not None and performance.min_price <= max_price


def _performance_satisfies_max_runtime(performance: Performance, max_minutes: int) -> bool:
    minutes = _runtime_minutes(performance.runtime)
    return minutes is not None and minutes <= max_minutes


def _performance_satisfies_schedule(performance: Performance, schedule_intent: dict) -> bool:
    schedule_text = performance.schedule_info or ""
    if not schedule_text:
        return False
    days = schedule_intent.get("days") or []
    if days and not any(day in schedule_text for day in days):
        return False
    time_of_day = schedule_intent.get("time_of_day")
    if time_of_day and not _schedule_matches_time_of_day(schedule_text, time_of_day):
        return False
    return True


def _cheapest_candidate(candidates: list[Candidate]) -> Candidate | None:
    priced = [
        candidate
        for candidate in candidates
        if candidate.performance.is_free or candidate.performance.min_price is not None
    ]
    if not priced:
        return None
    return min(priced, key=lambda candidate: 0 if candidate.performance.is_free else candidate.performance.min_price)


def _candidate_features(performance: Performance) -> list[str]:
    features = []
    if performance.is_child:
        features.append("child")
    if performance.is_festival:
        features.append("festival")
    if performance.openrun:
        features.append("openrun")
    if performance.is_daehakro:
        features.append("daehakro")
    if performance.is_musical_license:
        features.append("musical_license")
    if performance.is_musical_create:
        features.append("musical_create")
    return features


def _short_text(value: str, max_length: int) -> str:
    value = (value or "").strip()
    if len(value) <= max_length:
        return value
    return f"{value[:max_length].rstrip()}..."


def _candidate_payload(candidate: Candidate) -> dict:
    performance = candidate.performance
    venue = getattr(performance, "venue", None)
    min_price = performance.min_price
    max_price = performance.max_price
    price_label = "무료" if performance.is_free else None
    if price_label is None and min_price is not None and max_price is not None:
        price_label = f"{min_price:,}원" if min_price == max_price else f"{min_price:,}~{max_price:,}원"
    return {
        "performance_id": performance.performance_id,
        "title": performance.title,
        "genre": performance.genre,
        "genre_code": performance.genre_code,
        "region": " ".join(filter(None, [getattr(venue, "sido", ""), getattr(venue, "gugun", "")])) if venue else "",
        "venue": getattr(venue, "name", "") if venue else performance.facility_name,
        "start_date": performance.start_date.isoformat() if performance.start_date else None,
        "end_date": performance.end_date.isoformat() if performance.end_date else None,
        "status": performance.status,
        "runtime": performance.runtime,
        "age_rating": performance.age_rating,
        "schedule_info": _short_text(performance.schedule_info, 80),
        "price": {
            "label": price_label,
            "min_price": min_price,
            "max_price": max_price,
            "is_free": performance.is_free,
        },
        "features": _candidate_features(performance),
        "synopsis": _short_text(performance.synopsis, 80),
        "candidate_score": candidate.score,
        "candidate_reasons": candidate.reasons[:2],
    }


def _availability_bonus(performance: Performance) -> float:
    today = timezone.localdate()
    if performance.start_date and performance.end_date and performance.start_date <= today <= performance.end_date:
        return 0.6
    if performance.start_date and performance.start_date > today:
        return 0.4
    return 0.1


def _popularity_bonus(performance: Performance) -> float:
    return round(min(log1p(max(performance.zzim_count, 0)), 3.0) * 0.15 + min(log1p(max(performance.view_count, 0)), 4.5) * 0.08, 4)


def _fallback_reasons(performance: Performance) -> list[str]:
    if performance.zzim_count > 0:
        return ["관심 등록이 있는 인기 공연입니다."]
    if performance.view_count > 0:
        return ["조회수가 있는 공연입니다."]
    return ["공연 일정과 기본 조건이 추천 후보에 적합합니다."]


def _reason_for_key(key: str) -> str:
    dimension, value = _split_vector_key(key)
    if dimension == "genre":
        return f"선호 장르와 맞는 공연입니다. ({value})"
    if dimension == "region":
        return f"선호 지역과 가까운 공연입니다. ({value})"
    if dimension == "price":
        return f"선호 가격대와 비슷합니다. ({value})"
    if dimension == "feature":
        return f"선호 공연 특징과 맞습니다. ({value})"
    if dimension == "keyword":
        return f"최근 검색어와 연관이 있습니다. ({value})"
    return "사용자 취향과 유사합니다."


def _price_bucket(performance: Performance) -> str:
    if performance.is_free:
        return "free"
    price = performance.min_price or performance.max_price
    if price is None:
        return "unknown"
    if price < 30000:
        return "low"
    if price <= 100000:
        return "mid"
    return "high"


def _split_csv(value: str):
    return [item.strip() for item in (value or "").split(",") if item.strip()]


def _split_vector_key(key: str):
    if ":" not in key:
        return key, ""
    return key.split(":", 1)


def _normalize_token(value: str) -> str:
    return (value or "").strip().lower().replace(" ", "").replace("-", "_")


def _contains_any(value: str, terms: list[str]) -> bool:
    lowered = (value or "").lower()
    normalized = _normalize_token(value)
    return any((term or "").lower() in lowered or _normalize_token(term) in normalized for term in terms)


def _text_tokens(value: str, limit=5):
    normalized = (value or "").replace("[", " ").replace("]", " ").replace(":", " ")
    tokens = []
    for token in normalized.split():
        token = _normalize_token(token)
        if len(token) >= 2 and token not in tokens:
            tokens.append(token)
        if len(tokens) >= limit:
            break
    return tokens
