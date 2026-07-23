import logging
import math
from urllib.parse import parse_qsl, urlencode, urlsplit, urlunsplit

from django.conf import settings
from django.contrib.auth.tokens import default_token_generator
from django.core.mail import send_mail
from django.db import transaction
from django.template.loader import render_to_string
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework_simplejwt.tokens import RefreshToken

logger = logging.getLogger(__name__)

PROVIDER_NAMES = {
    "local": "이메일과 비밀번호",
    "google": "Google",
    "kakao": "Kakao",
    "naver": "Naver",
}


def _url_with_query(base_url, **params):
    parts = urlsplit(base_url)
    query = dict(parse_qsl(parts.query, keep_blank_values=True))
    query.update(params)
    return urlunsplit((parts.scheme, parts.netloc, parts.path, urlencode(query), parts.fragment))


def _send_user_email(*, subject, template_name, context, recipient, user_id):
    try:
        body = render_to_string(template_name, context)
        return bool(
            send_mail(
                subject=subject,
                message=body,
                from_email=settings.DEFAULT_FROM_EMAIL,
                recipient_list=[recipient],
                fail_silently=False,
            )
        )
    except Exception as exc:  # SMTP failures must not disclose account existence.
        logger.warning(
            "Account recovery email delivery failed user_id=%s error_type=%s",
            user_id,
            type(exc).__name__,
        )
        return False


def send_password_reset_email(user):
    uid = urlsafe_base64_encode(force_bytes(user.pk))
    token = default_token_generator.make_token(user)
    reset_url = _url_with_query(
        settings.FRONTEND_PASSWORD_RESET_URL,
        uid=uid,
        token=token,
    )
    timeout_minutes = max(1, math.ceil(settings.PASSWORD_RESET_TIMEOUT / 60))
    return _send_user_email(
        subject="[CulturePick] 비밀번호 재설정 안내",
        template_name="emails/password_reset.txt",
        context={"reset_url": reset_url, "timeout_minutes": timeout_minutes},
        recipient=user.email,
        user_id=user.pk,
    )


def send_account_recovery_email(user):
    return _send_user_email(
        subject="[CulturePick] 계정 가입 방식 안내",
        template_name="emails/account_recovery.txt",
        context={
            "provider": user.provider,
            "provider_name": PROVIDER_NAMES.get(user.provider, user.provider),
            "login_url": settings.FRONTEND_LOGIN_URL,
            "password_reset_url": settings.FRONTEND_PASSWORD_RESET_URL,
        },
        recipient=user.email,
        user_id=user.pk,
    )


def change_user_password_and_revoke_sessions(
    user,
    new_password,
    *,
    additional_update_fields=(),
):
    """Change a password and revoke all JWTs issued for the old version."""
    raw_refresh_token = user.refresh_token
    if raw_refresh_token:
        try:
            # A savepoint keeps a blacklist database failure from breaking the
            # surrounding ATOMIC_REQUESTS transaction.
            with transaction.atomic():
                RefreshToken(raw_refresh_token).blacklist()
        except Exception as exc:
            logger.warning(
                "Refresh token blacklist failed during password reset user_id=%s error_type=%s",
                user.pk,
                type(exc).__name__,
            )

    user.set_password(new_password)
    user.auth_version += 1
    user.refresh_token = ""
    user.refresh_token_expires_at = None
    user.save(
        update_fields={
            "password",
            "auth_version",
            "refresh_token",
            "refresh_token_expires_at",
            "updated_at",
            *additional_update_fields,
        }
    )


def reset_local_user_password(user, new_password):
    """Backward-compatible entry point used by the reset confirmation."""
    change_user_password_and_revoke_sessions(user, new_password)
