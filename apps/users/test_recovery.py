import re
from datetime import datetime, timedelta
from urllib.parse import parse_qs, urlparse
from unittest.mock import call, patch

from django.contrib.auth import get_user_model
from django.contrib.auth.tokens import default_token_generator
from django.core import mail
from django.core.cache import cache
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from django.utils.encoding import force_bytes
from django.utils.http import urlsafe_base64_encode
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import RefreshToken

from apps.users.tasks import deliver_account_recovery_email, deliver_password_reset_email

User = get_user_model()


@override_settings(
    EMAIL_BACKEND="django.core.mail.backends.locmem.EmailBackend",
    DEFAULT_FROM_EMAIL="noreply@example.com",
    FRONTEND_PASSWORD_RESET_URL="https://culturepick.netlify.app/find-account",
    FRONTEND_LOGIN_URL="https://culturepick.netlify.app/login",
    PASSWORD_RESET_TIMEOUT=3600,
)
class AccountRecoveryAPITests(APITestCase):
    def setUp(self):
        cache.clear()
        if hasattr(mail, "outbox"):
            mail.outbox.clear()
        self.user = User.objects.create_user(
            email="recover@example.com",
            password="OldValidPass123!",
            nickname="recover",
        )

    def tearDown(self):
        cache.clear()

    def _request_reset_link(self):
        with patch("apps.users.views.deliver_password_reset_email.delay") as enqueue:
            response = self.client.post(
                reverse("password_reset_request"),
                {"email": self.user.email},
                format="json",
            )
        self.assertEqual(response.status_code, status.HTTP_200_OK)
        enqueue.assert_called_once_with("recover@example.com")
        self.assertEqual(len(mail.outbox), 0)

        deliver_password_reset_email.run("recover@example.com")
        self.assertEqual(len(mail.outbox), 1)

        url_match = re.search(r"https://\S+", mail.outbox[0].body)
        self.assertIsNotNone(url_match)
        query = parse_qs(urlparse(url_match.group(0)).query)
        return response, query["uid"][0], query["token"][0]

    def test_password_reset_request_does_not_reveal_whether_email_exists(self):
        with patch("apps.users.views.deliver_password_reset_email.delay") as enqueue:
            known_response = self.client.post(
                reverse("password_reset_request"),
                {"email": "  Recover@Example.COM  "},
                format="json",
            )
            unknown_response = self.client.post(
                reverse("password_reset_request"),
                {"email": "  Missing@Example.COM  "},
                format="json",
            )

        self.assertEqual(known_response.status_code, status.HTTP_200_OK)
        self.assertEqual(unknown_response.status_code, status.HTTP_200_OK)
        self.assertEqual(unknown_response.data, known_response.data)
        self.assertEqual(
            enqueue.call_args_list,
            [call("recover@example.com"), call("missing@example.com")],
        )
        self.assertTrue(all(len(item.args) == 1 and not item.kwargs for item in enqueue.call_args_list))
        self.assertEqual(len(mail.outbox), 0)

    def test_password_reset_request_ignores_social_inactive_and_banned_accounts(self):
        social = User.objects.create(
            email="social-reset@example.com",
            provider=User.Provider.GOOGLE,
            provider_id="google-reset",
        )
        social.set_unusable_password()
        social.save()
        inactive = User.objects.create_user(
            email="inactive-reset@example.com",
            password="OldValidPass123!",
            status=User.Status.INACTIVE,
        )
        banned = User.objects.create_user(
            email="banned-reset@example.com",
            password="OldValidPass123!",
            status=User.Status.BANNED,
        )

        with patch("apps.users.views.deliver_password_reset_email.delay") as enqueue:
            for account in (social, inactive, banned):
                response = self.client.post(
                    reverse("password_reset_request"),
                    {"email": account.email},
                    format="json",
                )
                self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(enqueue.call_count, 3)
        for account in (social, inactive, banned):
            deliver_password_reset_email.run(account.email)

        self.assertEqual(len(mail.outbox), 0)
        inactive.refresh_from_db()
        banned.refresh_from_db()
        self.assertEqual(inactive.status, User.Status.INACTIVE)
        self.assertEqual(banned.status, User.Status.BANNED)

    def test_valid_reset_changes_password_and_revokes_stored_refresh_token(self):
        refresh = RefreshToken.for_user(self.user)
        self.user.refresh_token = str(refresh)
        self.user.refresh_token_expires_at = timezone.now() + timedelta(days=14)
        self.user.save(update_fields=["refresh_token", "refresh_token_expires_at"])
        _, uid, token = self._request_reset_link()

        response = self.client.post(
            reverse("password_reset_confirm"),
            {
                "uid": uid,
                "token": token,
                "new_password": "NewValidPass456!",
                "new_password_confirm": "NewValidPass456!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewValidPass456!"))
        self.assertEqual(self.user.refresh_token, "")
        self.assertIsNone(self.user.refresh_token_expires_at)
        self.assertTrue(BlacklistedToken.objects.filter(token__jti=refresh["jti"]).exists())

        reused_response = self.client.post(
            reverse("password_reset_confirm"),
            {
                "uid": uid,
                "token": token,
                "new_password": "AnotherValidPass789!",
                "new_password_confirm": "AnotherValidPass789!",
            },
            format="json",
        )
        self.assertEqual(reused_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_invalid_and_expired_reset_tokens_are_rejected(self):
        uid = urlsafe_base64_encode(force_bytes(self.user.pk))
        invalid_response = self.client.post(
            reverse("password_reset_confirm"),
            {
                "uid": uid,
                "token": "invalid-token",
                "new_password": "NewValidPass456!",
                "new_password_confirm": "NewValidPass456!",
            },
            format="json",
        )
        self.assertEqual(invalid_response.status_code, status.HTTP_400_BAD_REQUEST)

        issued_at = datetime(2026, 1, 1, 12, 0, 0)
        with patch.object(default_token_generator, "_now", return_value=issued_at):
            expired_token = default_token_generator.make_token(self.user)
        with patch.object(
            default_token_generator,
            "_now",
            return_value=issued_at + timedelta(seconds=3601),
        ):
            expired_response = self.client.post(
                reverse("password_reset_confirm"),
                {
                    "uid": uid,
                    "token": expired_token,
                    "new_password": "NewValidPass456!",
                    "new_password_confirm": "NewValidPass456!",
                },
                format="json",
            )
        self.assertEqual(expired_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("OldValidPass123!"))

    def test_reset_confirmation_validates_password_and_confirmation(self):
        _, uid, token = self._request_reset_link()
        mismatch_response = self.client.post(
            reverse("password_reset_confirm"),
            {
                "uid": uid,
                "token": token,
                "new_password": "NewValidPass456!",
                "new_password_confirm": "DifferentPass456!",
            },
            format="json",
        )
        weak_response = self.client.post(
            reverse("password_reset_confirm"),
            {
                "uid": uid,
                "token": token,
                "new_password": "weak",
                "new_password_confirm": "weak",
            },
            format="json",
        )

        self.assertEqual(mismatch_response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(weak_response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_account_recovery_sends_provider_only_to_active_account_owner(self):
        social = User.objects.create(
            email="social-recovery@example.com",
            provider=User.Provider.KAKAO,
            provider_id="kakao-recovery",
        )
        social.set_unusable_password()
        social.save()

        with patch("apps.users.views.deliver_account_recovery_email.delay") as enqueue:
            known_response = self.client.post(
                reverse("account_recovery"),
                {"email": "  Social-Recovery@Example.COM  "},
                format="json",
            )
            unknown_response = self.client.post(
                reverse("account_recovery"),
                {"email": " Missing-Recovery@Example.COM "},
                format="json",
            )

        self.assertEqual(known_response.status_code, status.HTTP_200_OK)
        self.assertEqual(unknown_response.status_code, status.HTTP_200_OK)
        self.assertEqual(unknown_response.data, known_response.data)
        self.assertEqual(
            enqueue.call_args_list,
            [
                call("social-recovery@example.com"),
                call("missing-recovery@example.com"),
            ],
        )
        self.assertTrue(all(len(item.args) == 1 and not item.kwargs for item in enqueue.call_args_list))
        self.assertEqual(len(mail.outbox), 0)

        deliver_account_recovery_email.run("social-recovery@example.com")
        self.assertEqual(len(mail.outbox), 1)
        self.assertIn("Kakao", mail.outbox[0].body)
        self.assertIn("https://culturepick.netlify.app/login", mail.outbox[0].body)

        mail.outbox.clear()
        deliver_account_recovery_email.run("missing-recovery@example.com")
        self.assertEqual(len(mail.outbox), 0)

    def test_account_recovery_does_not_reactivate_inactive_or_banned_accounts(self):
        inactive = User.objects.create_user(
            email="inactive-recovery@example.com",
            password="OldValidPass123!",
            status=User.Status.INACTIVE,
        )
        banned = User.objects.create_user(
            email="banned-recovery@example.com",
            password="OldValidPass123!",
            status=User.Status.BANNED,
        )

        with patch("apps.users.views.deliver_account_recovery_email.delay") as enqueue:
            for account in (inactive, banned):
                response = self.client.post(
                    reverse("account_recovery"),
                    {"email": account.email},
                    format="json",
                )
                self.assertEqual(response.status_code, status.HTTP_200_OK)

        self.assertEqual(enqueue.call_count, 2)
        for account in (inactive, banned):
            deliver_account_recovery_email.run(account.email)

        self.assertEqual(len(mail.outbox), 0)
        inactive.refresh_from_db()
        banned.refresh_from_db()
        self.assertEqual(inactive.status, User.Status.INACTIVE)
        self.assertEqual(banned.status, User.Status.BANNED)

    def test_email_delivery_failure_still_returns_generic_success(self):
        with patch(
            "apps.users.views.deliver_password_reset_email.delay",
            side_effect=RuntimeError("broker unavailable"),
        ):
            password_reset_response = self.client.post(
                reverse("password_reset_request"),
                {"email": self.user.email},
                format="json",
            )

        with patch(
            "apps.users.views.deliver_account_recovery_email.delay",
            side_effect=RuntimeError("broker unavailable"),
        ):
            account_recovery_response = self.client.post(
                reverse("account_recovery"),
                {"email": self.user.email},
                format="json",
            )

        self.assertEqual(password_reset_response.status_code, status.HTTP_200_OK)
        self.assertEqual(account_recovery_response.status_code, status.HTTP_200_OK)
        self.assertNotIn(self.user.email, str(password_reset_response.data))
        self.assertNotIn(self.user.email, str(account_recovery_response.data))

        with patch("apps.users.recovery.send_mail", side_effect=RuntimeError("SMTP unavailable")):
            deliver_password_reset_email.run(self.user.email)
            deliver_account_recovery_email.run(self.user.email)

        self.assertEqual(len(mail.outbox), 0)

    def test_password_reset_request_is_scoped_and_throttled(self):
        cache.clear()
        with patch("apps.users.views.deliver_password_reset_email.delay") as enqueue:
            for index in range(5):
                response = self.client.post(
                    reverse("password_reset_request"),
                    {"email": f"missing-{index}@example.com"},
                    format="json",
                )
                self.assertEqual(response.status_code, status.HTTP_200_OK)

            throttled_response = self.client.post(
                reverse("password_reset_request"),
                {"email": "missing-6@example.com"},
                format="json",
            )

        self.assertEqual(enqueue.call_count, 5)
        self.assertEqual(throttled_response.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
