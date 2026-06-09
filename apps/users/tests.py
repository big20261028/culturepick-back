from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from unittest.mock import patch

User = get_user_model()


class LocalAuthAPITests(APITestCase):
    def test_register_rejects_weak_password(self):
        response = self.client.post(
            reverse("register"),
            {
                "email": "weak@example.com",
                "password": "123",
                "password_confirm": "123",
                "nickname": "weak",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(email="weak@example.com").exists())

    def test_register_accepts_valid_password(self):
        response = self.client.post(
            reverse("register"),
            {
                "email": "valid@example.com",
                "password": "ValidPass123!",
                "password_confirm": "ValidPass123!",
                "nickname": "valid",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertTrue(User.objects.filter(email="valid@example.com").exists())

    def test_register_accepts_missing_nickname(self):
        response = self.client.post(
            reverse("register"),
            {
                "email": "no-nickname@example.com",
                "password": "ValidPass123!",
                "password_confirm": "ValidPass123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        user = User.objects.get(email="no-nickname@example.com")
        self.assertEqual(user.nickname, "")


class SocialAuthAPITests(APITestCase):
    def test_google_social_login_creates_user_and_tokens(self):
        def fake_google_strategy(code, redirect_uri):
            self.assertEqual(code, "valid-code")
            self.assertEqual(redirect_uri, "http://localhost:3000/oauth/google/callback")
            return {
                "provider_id": "google-sub-1",
                "email": "google@example.com",
                "nickname": "Google User",
            }

        with patch.dict("apps.users.views.SOCIAL_AUTH_STRATEGIES", {"google": fake_google_strategy}):
            response = self.client.post(
                reverse("social_login"),
                {
                    "provider": "google",
                    "code": "valid-code",
                    "redirect_uri": "http://localhost:3000/oauth/google/callback",
                },
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertIn("access", response.data)
        self.assertIn("refresh", response.data)

        user = User.objects.get(email="google@example.com")
        self.assertEqual(user.provider, User.Provider.GOOGLE)
        self.assertEqual(user.provider_id, "google-sub-1")
        self.assertFalse(user.has_usable_password())
        self.assertEqual(user.refresh_token, response.data["refresh"])

    def test_google_social_login_rejects_existing_local_user(self):
        User.objects.create_user(
            email="same@example.com",
            password="ValidPass123!",
            nickname="Local User",
        )

        def fake_google_strategy(code, redirect_uri):
            return {
                "provider_id": "google-sub-2",
                "email": "same@example.com",
                "nickname": "Google User",
            }

        with patch.dict("apps.users.views.SOCIAL_AUTH_STRATEGIES", {"google": fake_google_strategy}):
            response = self.client.post(
                reverse("social_login"),
                {
                    "provider": "google",
                    "code": "valid-code",
                    "redirect_uri": "http://localhost:3000/oauth/google/callback",
                },
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_google_social_login_rejects_provider_id_mismatch(self):
        user = User.objects.create(
            email="google@example.com",
            provider=User.Provider.GOOGLE,
            provider_id="google-sub-old",
            nickname="Google User",
        )
        user.set_unusable_password()
        user.save()

        def fake_google_strategy(code, redirect_uri):
            return {
                "provider_id": "google-sub-new",
                "email": "google@example.com",
                "nickname": "Google User",
            }

        with patch.dict("apps.users.views.SOCIAL_AUTH_STRATEGIES", {"google": fake_google_strategy}):
            response = self.client.post(
                reverse("social_login"),
                {
                    "provider": "google",
                    "code": "valid-code",
                    "redirect_uri": "http://localhost:3000/oauth/google/callback",
                },
                format="json",
            )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_social_login_rejects_unsupported_provider(self):
        response = self.client.post(
            reverse("social_login"),
            {
                "provider": "unsupported",
                "code": "valid-code",
                "redirect_uri": "http://localhost:3000/oauth/callback",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
