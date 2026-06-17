from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from datetime import timedelta
from math import log1p

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
from .openai_client import OpenAIRecommendationError, request_openai_recommendations


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
    "AAAA": ["??", "play", "drama"],
    "GGGA": ["???", "musical"],
    "CCCA": ["???", "classic", "orchestra", "?????"],
    "CCCC": ["??", "korean music", "koreanmusic"],
    "CCCD": ["???", "concert", "??", "band"],
    "BBBC": ["??", "??", "dance", "ballet", "??"],
    "EEEA": ["???", "??", "magic", "circus"],
    "EEEB": ["??", "complex"],
}

REQUEST_REGION_TERMS = {
    "??": ["??", "seoul"],
    "??": ["??", "gyeonggi"],
    "??": ["??", "incheon"],
    "??": ["??", "busan"],
    "??": ["??", "daegu"],
    "??": ["??", "daejeon"],
    "??": ["??", "gwangju"],
    "??": ["??", "ulsan"],
    "??": ["??", "sejong"],
    "??": ["??", "gangwon"],
    "??": ["??", "chungbuk"],
    "??": ["??", "chungnam"],
    "??": ["??", "jeonbuk"],
    "??": ["??", "jeonnam"],
    "??": ["??", "gyeongbuk"],
    "??": ["??", "gyeongnam"],
    "??": ["??", "jeju"],
}

REQUEST_PRICE_TERMS = {
    "free": ["??", "free"],
    "low": ["??", "?", "3??", "30000", "low"],
    "mid": ["10??", "100000", "???", "??", "mid"],
    "high": ["????", "??", "vip", "high"],
}

REQUEST_FEATURE_TERMS = {
    "child": ["??", "???", "??", "family", "kid", "children"],
    "festival": ["??", "????", "festival"],
    "openrun": ["???", "openrun", "open run"],
}


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


def get_or_build_performance_vector(performance: Performance) -> PerformanceVector:
    vector, _ = PerformanceVector.objects.get_or_create(performance=performance)
    if vector.vector_data and vector.version == PERFORMANCE_VECTOR_VERSION:
        return vector

    vector.vector_data = build_performance_vector_data(performance)
    vector.source_summary = build_performance_source_summary(performance)
    vector.version = PERFORMANCE_VECTOR_VERSION
    vector.save(update_fields=["vector_data", "source_summary", "version", "updated_at"])
    return vector


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


def get_recommendation_candidates(user=None, message="", limit=30, pool_size=500) -> tuple[dict, list[Candidate]]:
    profile = get_or_build_user_profile(user)
    user_vector = profile.vector_data if profile else {}
    request_vector = build_request_vector(message)
    combined_vector = _merge_preference_vectors(user_vector, request_vector)
    profile_snapshot = {
        "vector_data": combined_vector,
        "user_vector_data": user_vector,
        "request_vector_data": request_vector,
        "source_summary": profile.source_summary if profile else {},
        "is_personalized": bool(user_vector),
        "has_request_signal": bool(request_vector),
    }

    queryset = _candidate_queryset(user, combined_vector, pool_size)
    candidates = [_score_candidate(performance, combined_vector) for performance in queryset]
    candidates.sort(key=lambda candidate: candidate.score, reverse=True)
    return profile_snapshot, candidates[:limit]


def build_request_vector(message: str) -> dict[str, float]:
    scores = defaultdict(float)
    if not message:
        return {}

    for genre_code, terms in REQUEST_GENRE_TERMS.items():
        if _contains_any(message, terms):
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

    for token in _text_tokens(message, limit=8):
        scores[f"keyword:{token}"] += 0.3

    return _normalize_scores(scores)


def _candidate_queryset(user, user_vector: dict[str, float], pool_size: int):
    today = timezone.localdate()
    queryset = (
        Performance.objects.select_related("venue")
        .filter(Q(end_date__isnull=True) | Q(end_date__gte=today))
        .order_by("-zzim_count", "-view_count", "start_date", "title")
    )

    if user and user.is_authenticated:
        selected_ids = UsersPerformanceAction.objects.filter(user=user).values_list("performance_id", flat=True)
        queryset = queryset.exclude(performance_id__in=selected_ids)

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


def _score_candidate(performance: Performance, user_vector: dict[str, float]) -> Candidate:
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


def create_ai_recommendation(user, message="", limit=5, candidate_limit=30) -> RecommendationSession:
    profile_snapshot, candidates = get_recommendation_candidates(
        user=user,
        message=message,
        limit=max(candidate_limit, limit),
    )
    candidate_snapshot = [_candidate_payload(candidate) for candidate in candidates]

    session = RecommendationSession.objects.create(
        user=user if user and user.is_authenticated else None,
        request_text=message or "",
        provider="openai",
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

    fallback_items = _fallback_items(candidates, limit)
    session.provider = "rule_based"
    session.fallback_used = True
    session.parsed_response = {
        "summary": "추천 후보를 기준으로 공연을 골랐습니다.",
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
        session.provider != "openai"
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

    if session.provider != "openai":
        rejection_reasons.append("provider_not_openai")
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


def _fallback_items(candidates: list[Candidate], limit: int) -> list[dict]:
    return [
        {
            "performance": candidate.performance,
            "rank": index + 1,
            "score": candidate.score,
            "reason": candidate.reasons[0] if candidate.reasons else "추천 후보 점수가 높습니다.",
        }
        for index, candidate in enumerate(candidates[:limit])
    ]


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


def _candidate_payload(candidate: Candidate) -> dict:
    performance = candidate.performance
    venue = getattr(performance, "venue", None)
    return {
        "performance_id": performance.performance_id,
        "title": performance.title,
        "genre": performance.genre,
        "genre_code": performance.genre_code,
        "region": getattr(venue, "sido", "") if venue else "",
        "venue": getattr(venue, "name", "") if venue else performance.facility_name,
        "period": {
            "start_date": performance.start_date.isoformat() if performance.start_date else None,
            "end_date": performance.end_date.isoformat() if performance.end_date else None,
        },
        "status": performance.status,
        "price": {
            "min_price": performance.min_price,
            "max_price": performance.max_price,
            "is_free": performance.is_free,
        },
        "synopsis": (performance.synopsis or "")[:500],
        "candidate_score": candidate.score,
        "candidate_reasons": candidate.reasons,
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
