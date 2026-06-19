import logging

from django.contrib.auth.models import AnonymousUser

from .models import QnALog, SearchLog, ViewLog

logger = logging.getLogger(__name__)


def request_user_or_none(request):
    user = getattr(request, "user", None)
    if not user or isinstance(user, AnonymousUser) or not user.is_authenticated:
        return None
    return user


def record_search_log(*, user=None, keyword="", filter_region="", filter_genre="", filter_status=""):
    log = SearchLog.objects.create(
        user=user,
        keyword=keyword or "",
        filter_region=filter_region or "",
        filter_genre=filter_genre or "",
        filter_status=filter_status or "",
    )
    _mark_recommendation_profile_stale(user)
    return log


def record_view_log(*, user=None, performance_id="", log_type=""):
    log = ViewLog.objects.create(
        user=user,
        performance_id=performance_id,
        log_type=log_type or "",
    )
    _mark_recommendation_profile_stale(user)
    return log


def record_qna_log(*, user=None, question="", answer=""):
    return QnALog.objects.create(
        user=user,
        question=question,
        answer=answer or "",
    )


def safe_record_search_log(**kwargs):
    try:
        return record_search_log(**kwargs)
    except Exception as exc:
        logger.warning("failed to record search log: %s", exc, exc_info=True)
        return None


def safe_record_view_log(**kwargs):
    try:
        return record_view_log(**kwargs)
    except Exception as exc:
        logger.warning("failed to record view log: %s", exc, exc_info=True)
        return None


def _mark_recommendation_profile_stale(user):
    try:
        from apps.recommendations.services import mark_user_recommendation_profile_stale

        mark_user_recommendation_profile_stale(user)
    except Exception as exc:
        logger.warning("failed to mark recommendation profile stale: %s", exc, exc_info=True)
