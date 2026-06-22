from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from unittest.mock import patch

from apps.performances.models import Performance, UsersPerformanceAction, Venue

User = get_user_model()


class LocalAuthAPITests(APITestCase):
    def test_register_rejects_invalid_email_format(self):
        response = self.client.post(
            reverse("register"),
            {
                "email": "invalid-email",
                "password": "ValidPass123!",
                "password_confirm": "ValidPass123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(email="invalid-email").exists())

    def test_register_rejects_email_with_emoji(self):
        response = self.client.post(
            reverse("register"),
            {
                "email": "emoji😀@example.com",
                "password": "ValidPass123!",
                "password_confirm": "ValidPass123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(email="emoji😀@example.com").exists())

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

    def test_register_rejects_password_without_required_character_groups(self):
        response = self.client.post(
            reverse("register"),
            {
                "email": "no-special@example.com",
                "password": "ValidPass123",
                "password_confirm": "ValidPass123",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(User.objects.filter(email="no-special@example.com").exists())

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


class MyPagePerformanceAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="mypage@example.com",
            password="ValidPass123!",
            nickname="mypage",
        )
        self.other_user = User.objects.create_user(
            email="other-mypage@example.com",
            password="ValidPass123!",
            nickname="other",
        )
        self.venue = Venue.objects.create(
            venue_id="FCMYPAGE",
            name="My Page Hall",
            sido="서울특별시",
            gugun="종로구",
            address="서울특별시 종로구",
        )
        self.interest_performance = Performance.objects.create(
            performance_id="PFMYPAGE_INTEREST",
            title="Interest Performance",
            genre="뮤지컬",
            genre_code="GGGA",
            venue=self.venue,
        )
        self.watchlist_performance = Performance.objects.create(
            performance_id="PFMYPAGE_WATCH",
            title="Watchlist Performance",
            genre="연극",
            genre_code="AAAA",
            venue=self.venue,
        )
        self.other_performance = Performance.objects.create(
            performance_id="PFMYPAGE_OTHER",
            title="Other User Performance",
            genre="뮤지컬",
            genre_code="GGGA",
            venue=self.venue,
        )
        UsersPerformanceAction.objects.create(
            user=self.user,
            performance=self.interest_performance,
            action_type=UsersPerformanceAction.ActionType.INTEREST,
        )
        UsersPerformanceAction.objects.create(
            user=self.user,
            performance=self.watchlist_performance,
            action_type=UsersPerformanceAction.ActionType.WATCHLIST,
        )
        UsersPerformanceAction.objects.create(
            user=self.other_user,
            performance=self.other_performance,
            action_type=UsersPerformanceAction.ActionType.INTEREST,
        )

    def test_my_interest_performances_require_authentication(self):
        response = self.client.get(reverse("my_interest_performances"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_my_interest_performances_returns_only_current_user_interest_items(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse("my_interest_performances"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["type"], "interest")
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(
            response.data["results"][0]["performance_id"],
            "PFMYPAGE_INTEREST",
        )
        self.assertTrue(response.data["results"][0]["is_interested"])
        self.assertFalse(response.data["results"][0]["is_watchlisted"])

    def test_my_watchlist_performances_returns_only_current_user_watchlist_items(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse("my_watchlist_performances"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["type"], "watchlist")
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(
            response.data["results"][0]["performance_id"],
            "PFMYPAGE_WATCH",
        )
        self.assertFalse(response.data["results"][0]["is_interested"])
        self.assertTrue(response.data["results"][0]["is_watchlisted"])


class MyProfileAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="profile@example.com",
            password="ValidPass123!",
            nickname="old_nickname",
            phone="010-0000-0000",
        )

    def test_my_profile_requires_authentication(self):
        response = self.client.get(reverse("my_profile"))

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_my_profile_returns_current_user_data(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.get(reverse("my_profile"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["email"], "profile@example.com")
        self.assertEqual(response.data["nickname"], "old_nickname")
        self.assertEqual(response.data["display_name"], "old_nickname")
        self.assertEqual(response.data["phone"], "010-0000-0000")
        self.assertEqual(response.data["provider"], User.Provider.LOCAL)
        self.assertTrue(response.data["can_change_password"])
        self.assertTrue(response.data["requires_password_verification"])

    def test_my_profile_display_name_falls_back_to_email_without_nickname(self):
        user = User.objects.create_user(
            email="display@example.com",
            password="ValidPass123!",
        )
        self.client.force_authenticate(user=user)

        response = self.client.get(reverse("my_profile"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["nickname"], "")
        self.assertEqual(response.data["display_name"], "display@example.com")

    def test_password_verify_rejects_wrong_password(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("my_password_verify"),
            {"password": "WrongPass123!"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn("verification_token", response.data)

    def test_profile_update_requires_verification_token(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            reverse("my_profile"),
            {"nickname": "new_nickname"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_403_FORBIDDEN)
        self.user.refresh_from_db()
        self.assertEqual(self.user.nickname, "old_nickname")

    def test_profile_update_changes_only_submitted_fields(self):
        self.client.force_authenticate(user=self.user)
        verify_response = self.client.post(
            reverse("my_password_verify"),
            {"password": "ValidPass123!"},
            format="json",
        )

        response = self.client.patch(
            reverse("my_profile"),
            {
                "verification_token": verify_response.data["verification_token"],
                "nickname": "new_nickname",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertEqual(self.user.nickname, "new_nickname")
        self.assertEqual(self.user.phone, "010-0000-0000")
        self.assertEqual(response.data["display_name"], "new_nickname")

    def test_profile_update_can_change_password(self):
        self.client.force_authenticate(user=self.user)
        verify_response = self.client.post(
            reverse("my_password_verify"),
            {"password": "ValidPass123!"},
            format="json",
        )

        response = self.client.patch(
            reverse("my_profile"),
            {
                "verification_token": verify_response.data["verification_token"],
                "new_password": "NewValidPass123!",
                "new_password_confirm": "NewValidPass123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("NewValidPass123!"))

    def test_profile_update_rejects_password_mismatch(self):
        self.client.force_authenticate(user=self.user)
        verify_response = self.client.post(
            reverse("my_password_verify"),
            {"password": "ValidPass123!"},
            format="json",
        )

        response = self.client.patch(
            reverse("my_profile"),
            {
                "verification_token": verify_response.data["verification_token"],
                "new_password": "NewValidPass123!",
                "new_password_confirm": "DifferentPass123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.user.refresh_from_db()
        self.assertTrue(self.user.check_password("ValidPass123!"))

    def test_social_profile_returns_password_flags(self):
        social_user = User.objects.create(
            email="social-profile@example.com",
            provider=User.Provider.GOOGLE,
            provider_id="google-social-profile",
            nickname="social",
        )
        social_user.set_unusable_password()
        social_user.save()
        self.client.force_authenticate(user=social_user)

        response = self.client.get(reverse("my_profile"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["provider"], User.Provider.GOOGLE)
        self.assertFalse(response.data["can_change_password"])
        self.assertFalse(response.data["requires_password_verification"])

    def test_social_profile_update_does_not_require_password_verification(self):
        social_user = User.objects.create(
            email="social-update@example.com",
            provider=User.Provider.GOOGLE,
            provider_id="google-social-update",
            nickname="old_social",
        )
        social_user.set_unusable_password()
        social_user.save()
        self.client.force_authenticate(user=social_user)

        response = self.client.patch(
            reverse("my_profile"),
            {"nickname": "new_social", "phone": "010-1111-2222"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        social_user.refresh_from_db()
        self.assertEqual(social_user.nickname, "new_social")
        self.assertEqual(social_user.phone, "010-1111-2222")

    def test_social_profile_update_rejects_password_change(self):
        social_user = User.objects.create(
            email="social-password@example.com",
            provider=User.Provider.GOOGLE,
            provider_id="google-social-password",
        )
        social_user.set_unusable_password()
        social_user.save()
        self.client.force_authenticate(user=social_user)

        response = self.client.patch(
            reverse("my_profile"),
            {
                "new_password": "NewValidPass123!",
                "new_password_confirm": "NewValidPass123!",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        social_user.refresh_from_db()
        self.assertFalse(social_user.has_usable_password())

    def test_social_password_verify_is_rejected(self):
        social_user = User.objects.create(
            email="social-verify@example.com",
            provider=User.Provider.GOOGLE,
            provider_id="google-social-verify",
        )
        social_user.set_unusable_password()
        social_user.save()
        self.client.force_authenticate(user=social_user)

        response = self.client.post(
            reverse("my_password_verify"),
            {"password": "anything"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertNotIn("verification_token", response.data)


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
