from unittest.mock import patch

from django.core.exceptions import ValidationError
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from rest_framework_simplejwt.token_blacklist.models import BlacklistedToken
from rest_framework_simplejwt.tokens import AccessToken, RefreshToken

from .models import User


class AuthVersionJWTTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="versioned@example.com",
            password="ValidPass123!",
            nickname="versioned",
        )
        self.other_user = User.objects.create_user(
            email="other-versioned@example.com",
            password="ValidPass123!",
        )

    def _login(self, user=None, password="ValidPass123!"):
        user = user or self.user
        return self.client.post(
            reverse("login"),
            {"email": user.email, "password": password},
            format="json",
        )

    def _authenticate(self, access_token):
        self.client.credentials(HTTP_AUTHORIZATION=f"Bearer {access_token}")

    def test_login_tokens_include_current_auth_version(self):
        response = self._login()

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(AccessToken(response.data["access"])["auth_version"], 1)
        self.assertEqual(RefreshToken(response.data["refresh"])["auth_version"], 1)
        self.assertEqual(set(response.data), {"access", "refresh"})

    def test_legacy_access_token_without_claim_is_accepted_only_at_version_one(self):
        legacy_access = RefreshToken.for_user(self.user).access_token
        self.assertNotIn("auth_version", legacy_access)
        self._authenticate(str(legacy_access))

        accepted = self.client.get(reverse("my_profile"))
        self.assertEqual(accepted.status_code, status.HTTP_200_OK)

        User.objects.filter(pk=self.user.pk).update(auth_version=2)
        rejected = self.client.get(reverse("my_profile"))
        self.assertEqual(rejected.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_malformed_auth_version_claim_is_rejected(self):
        refresh = RefreshToken.for_user(self.user)
        refresh["auth_version"] = "1"
        self._authenticate(str(refresh.access_token))

        response = self.client.get(reverse("my_profile"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_profile_password_change_revokes_old_access_and_refresh_only_for_user(self):
        login_response = self._login()
        old_access = login_response.data["access"]
        old_refresh = login_response.data["refresh"]
        old_refresh_jti = RefreshToken(old_refresh)["jti"]
        other_login = self._login(self.other_user)

        self._authenticate(old_access)
        verify_response = self.client.post(
            reverse("my_password_verify"),
            {"password": "ValidPass123!"},
            format="json",
        )
        change_response = self.client.patch(
            reverse("my_profile"),
            {
                "verification_token": verify_response.data["verification_token"],
                "new_password": "NewValidPass456!",
                "new_password_confirm": "NewValidPass456!",
            },
            format="json",
        )

        self.assertEqual(change_response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.auth_version, 2)
        self.assertEqual(self.user.refresh_token, "")
        self.assertTrue(self.user.check_password("NewValidPass456!"))
        self.assertTrue(
            BlacklistedToken.objects.filter(
                token__jti=old_refresh_jti,
            ).exists()
        )

        old_access_response = self.client.get(reverse("my_profile"))
        self.assertEqual(old_access_response.status_code, status.HTTP_401_UNAUTHORIZED)

        self.client.credentials()
        old_refresh_response = self.client.post(
            reverse("token_refresh"),
            {"refresh": old_refresh},
            format="json",
        )
        self.assertEqual(old_refresh_response.status_code, status.HTTP_401_UNAUTHORIZED)

        self._authenticate(other_login.data["access"])
        other_user_response = self.client.get(reverse("my_profile"))
        self.assertEqual(other_user_response.status_code, status.HTTP_200_OK)
        self.assertEqual(other_user_response.data["email"], self.other_user.email)

        self.client.credentials()
        new_login = self._login(password="NewValidPass456!")
        self.assertEqual(new_login.status_code, status.HTTP_200_OK)
        self.assertEqual(AccessToken(new_login.data["access"])["auth_version"], 2)

    def test_refresh_rejects_version_mismatch_even_if_token_is_still_stored(self):
        login_response = self._login()
        User.objects.filter(pk=self.user.pk).update(auth_version=2)

        response = self.client.post(
            reverse("token_refresh"),
            {"refresh": login_response.data["refresh"]},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)


class AccountStateTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="state@example.com",
            password="ValidPass123!",
        )

    def test_legacy_inactive_creation_defaults_to_protected_admin_reason(self):
        inactive = User.objects.create_user(
            email="legacy-inactive@example.com",
            password="ValidPass123!",
            status=User.Status.INACTIVE,
        )

        self.assertEqual(
            inactive.deactivation_reason,
            User.DeactivationReason.ADMIN_DISABLED,
        )
        self.assertIsNotNone(inactive.deactivated_at)
        self.assertFalse(inactive.can_recover_self_deactivated_account)

    def test_self_deactivation_and_recovery_are_explicit_state_transitions(self):
        refresh = RefreshToken.for_user(self.user)
        self.user.refresh_token = str(refresh)
        self.user.save(update_fields=["refresh_token"])

        self.user.deactivate()
        self.user.refresh_from_db()

        self.assertEqual(self.user.status, User.Status.INACTIVE)
        self.assertEqual(
            self.user.deactivation_reason,
            User.DeactivationReason.SELF_DEACTIVATED,
        )
        self.assertIsNotNone(self.user.deactivated_at)
        self.assertTrue(self.user.can_recover_self_deactivated_account)
        self.assertEqual(self.user.auth_version, 2)
        self.assertEqual(self.user.refresh_token, "")

        self.user.recover_self_deactivated_account()
        self.user.refresh_from_db()

        self.assertEqual(self.user.status, User.Status.ACTIVE)
        self.assertEqual(self.user.deactivation_reason, "")
        self.assertIsNone(self.user.deactivated_at)
        self.assertEqual(self.user.auth_version, 3)

    def test_admin_disabled_and_banned_accounts_cannot_use_self_recovery(self):
        self.user.deactivate(reason=User.DeactivationReason.ADMIN_DISABLED)
        with self.assertRaises(ValidationError):
            self.user.recover_self_deactivated_account()

        banned = User.objects.create_user(
            email="banned-state@example.com",
            password="ValidPass123!",
        )
        banned.ban()
        banned.refresh_from_db()

        self.assertEqual(banned.status, User.Status.BANNED)
        self.assertEqual(
            banned.deactivation_reason,
            User.DeactivationReason.POLICY_BANNED,
        )
        self.assertFalse(banned.can_recover_self_deactivated_account)
        with self.assertRaises(ValidationError):
            banned.recover_self_deactivated_account()

    def test_direct_status_change_is_normalized_and_revokes_sessions(self):
        self.user.refresh_token = str(RefreshToken.for_user(self.user))
        self.user.save(update_fields=["refresh_token"])

        self.user.status = User.Status.INACTIVE
        self.user.save(update_fields=["status"])
        self.user.refresh_from_db()

        self.assertEqual(
            self.user.deactivation_reason,
            User.DeactivationReason.ADMIN_DISABLED,
        )
        self.assertIsNotNone(self.user.deactivated_at)
        self.assertEqual(self.user.auth_version, 2)
        self.assertEqual(self.user.refresh_token, "")

    def test_policy_ban_reason_cannot_be_used_for_inactive_state(self):
        with self.assertRaises(ValidationError):
            self.user.deactivate(reason=User.DeactivationReason.POLICY_BANNED)

    def test_social_login_never_issues_tokens_for_inactive_account(self):
        inactive = User.objects.create_user(
            email="inactive-social@example.com",
            password=None,
            provider=User.Provider.GOOGLE,
            provider_id="google-inactive-id",
        )
        inactive.deactivate(reason=User.DeactivationReason.SECURITY_LOCK)

        with patch.dict(
            "apps.users.views.SOCIAL_AUTH_STRATEGIES",
            {
                "google": lambda code, redirect_uri: {
                    "email": inactive.email,
                    "provider_id": inactive.provider_id,
                    "nickname": "blocked",
                }
            },
        ):
            response = self.client.post(
                reverse("social_login"),
                {
                    "provider": "google",
                    "code": "valid-provider-code",
                    "redirect_uri": "https://culturepick.netlify.app/callback",
                },
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)
        self.assertNotIn("access", response.data)
        self.assertNotIn("refresh", response.data)
        inactive.refresh_from_db()
        self.assertEqual(inactive.refresh_token, "")
