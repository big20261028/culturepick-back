# common/exceptions.py
import logging

from rest_framework import status
from rest_framework.response import Response
from rest_framework.views import exception_handler

logger = logging.getLogger(__name__)


def custom_exception_handler(exc, context):
    """
    DRF 기본 예외 핸들러를 래핑해 일관된 에러 응답 형식을 반환합니다.

    응답 형식::

        {
            "code": "VALIDATION_ERROR",
            "message": "입력값이 올바르지 않습니다.",
            "detail": { ... }   # 필드별 오류 (선택)
        }
    """
    response = exception_handler(exc, context)

    if response is None:
        # DRF가 처리하지 못한 예외 → 500
        logger.error("Unhandled exception", exc_info=exc)
        return Response(
            {"code": "INTERNAL_ERROR", "message": "서버 내부 오류가 발생했습니다."},
            status=status.HTTP_500_INTERNAL_SERVER_ERROR,
        )

    response.data = {
        "code": _resolve_code(exc, response.status_code),
        "message": _resolve_message(exc, response.status_code),
        "detail": response.data,
    }
    return response


def _resolve_code(exc, status_code: int) -> str:
    code_map = {
        400: "BAD_REQUEST",
        401: "UNAUTHORIZED",
        403: "FORBIDDEN",
        404: "NOT_FOUND",
        405: "METHOD_NOT_ALLOWED",
        429: "TOO_MANY_REQUESTS",
    }
    return getattr(exc, "default_code", None) or code_map.get(status_code, "ERROR")


def _resolve_message(exc, status_code: int) -> str:
    message_map = {
        400: "입력값이 올바르지 않습니다.",
        401: "인증이 필요합니다.",
        403: "접근 권한이 없습니다.",
        404: "요청한 리소스를 찾을 수 없습니다.",
        429: "요청이 너무 많습니다. 잠시 후 다시 시도해주세요.",
    }
    return message_map.get(status_code, "오류가 발생했습니다.")
