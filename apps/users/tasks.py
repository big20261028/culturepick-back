from celery import shared_task
from django.contrib.auth import get_user_model

from .recovery import send_account_recovery_email, send_password_reset_email

User = get_user_model()


def normalize_recovery_email(email):
    """Return the canonical value placed on the recovery task queue."""
    return str(email).strip().casefold()


@shared_task(
    ignore_result=True,
    name="apps.users.tasks.deliver_password_reset_email",
)
def deliver_password_reset_email(email):
    """Look up an eligible local account and deliver its reset email."""
    normalized_email = normalize_recovery_email(email)
    user = User.objects.filter(
        email__iexact=normalized_email,
        provider=User.Provider.LOCAL,
        status=User.Status.ACTIVE,
    ).first()
    if user and user.has_usable_password():
        send_password_reset_email(user)


@shared_task(
    ignore_result=True,
    name="apps.users.tasks.deliver_account_recovery_email",
)
def deliver_account_recovery_email(email):
    """Look up an active account and deliver its provider guidance email."""
    normalized_email = normalize_recovery_email(email)
    user = User.objects.filter(
        email__iexact=normalized_email,
        status=User.Status.ACTIVE,
    ).first()
    if user:
        send_account_recovery_email(user)
