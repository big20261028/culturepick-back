from datetime import timedelta
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.performances.models import Performance, UsersPerformanceAction, Venue

from .models import (
    RecommendationFeedback,
    RecommendationItem,
    RecommendationSession,
    TrainingExampleCandidate,
)
from .services import get_recommendation_candidates

User = get_user_model()


class RecommendationAPITests(APITestCase):
    def setUp(self):
        today = timezone.localdate()
        self.user = User.objects.create_user(
            email="recommend-user@example.com",
            password="ValidPass123!",
            nickname="recommend-user",
        )
        self.venue = Venue.objects.create(
            venue_id="FCREC1",
            name="Recommendation Hall",
            sido="Seoul",
            gugun="Jongno",
        )
        self.liked_performance = Performance.objects.create(
            performance_id="PFREC-LIKED",
            title="Liked Musical",
            genre="Musical",
            genre_code="GGGA",
            start_date=today - timedelta(days=1),
            end_date=today + timedelta(days=10),
            status="Performing",
            min_price=50000,
            max_price=100000,
            venue=self.venue,
        )
        self.musical_candidate = Performance.objects.create(
            performance_id="PFREC-MUSICAL",
            title="Recommended Musical",
            genre="Musical",
            genre_code="GGGA",
            start_date=today + timedelta(days=5),
            end_date=today + timedelta(days=30),
            status="Upcoming",
            min_price=40000,
            max_price=90000,
            synopsis="A warm musical story.",
            zzim_count=5,
            view_count=20,
            venue=self.venue,
        )
        self.play_candidate = Performance.objects.create(
            performance_id="PFREC-PLAY",
            title="Other Play",
            genre="Play",
            genre_code="AAAA",
            start_date=today + timedelta(days=3),
            end_date=today + timedelta(days=20),
            status="Upcoming",
            min_price=30000,
            max_price=70000,
            venue=self.venue,
        )
        UsersPerformanceAction.objects.create(
            user=self.user,
            performance=self.liked_performance,
            action_type=UsersPerformanceAction.ActionType.INTEREST,
        )

    def test_candidate_scoring_uses_user_action_profile(self):
        _, candidates = get_recommendation_candidates(user=self.user, limit=5)

        self.assertGreaterEqual(len(candidates), 2)
        self.assertEqual(candidates[0].performance, self.musical_candidate)
        self.assertGreater(candidates[0].score, candidates[1].score)
        self.assertNotEqual(candidates[0].performance, self.liked_performance)

    def test_candidate_scoring_uses_request_prompt_signal(self):
        profile, candidates = get_recommendation_candidates(
            user=self.user,
            message="연극 추천",
            limit=5,
        )

        self.assertTrue(profile["has_request_signal"])
        self.assertEqual(candidates[0].performance, self.play_candidate)

    def test_candidate_api_returns_scored_candidates(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("recommendation_candidates"),
            {"prompt": "뮤지컬 추천해줘", "limit": 2},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["message"], "뮤지컬 추천해줘")
        self.assertEqual(response.data["total"], 2)
        self.assertIn("profile", response.data)
        self.assertIn("performance", response.data["candidates"][0])
        self.assertIn("reasons", response.data["candidates"][0])

    @override_settings(OPENAI_API_SECRET_KEY="")
    def test_ai_recommendation_falls_back_when_openai_is_not_configured(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("recommendation_ai"),
            {"message": "뮤지컬 추천해줘", "limit": 2},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["fallback_used"])
        self.assertEqual(response.data["validation_status"], RecommendationSession.ValidationStatus.FALLBACK)
        self.assertEqual(len(response.data["results"]), 2)
        self.assertEqual(RecommendationSession.objects.count(), 1)
        self.assertEqual(RecommendationItem.objects.count(), 2)

    @override_settings(OPENAI_API_SECRET_KEY="")
    def test_ai_recommendation_accepts_prompt_alias_and_candidate_preview(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("recommendation_ai"),
            {
                "prompt": "서울에서 볼 공연 추천",
                "limit": 1,
                "include_candidates": True,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["fallback_used"])
        self.assertIn("recommendations", response.data)
        self.assertIn("candidates", response.data)
        self.assertIn("performance_id", response.data["candidates"][0])
        session = RecommendationSession.objects.get(pk=response.data["session_id"])
        self.assertEqual(session.request_text, "서울에서 볼 공연 추천")

    @override_settings(OPENAI_API_SECRET_KEY="test-key", OPENAI_RECOMMENDATION_MODEL="test-model")
    @patch("apps.recommendations.services.request_openai_recommendations")
    def test_ai_recommendation_saves_valid_openai_response(self, mock_openai):
        mock_openai.return_value = (
            {
                "summary": "뮤지컬 선호를 바탕으로 추천했습니다.",
                "recommendations": [
                    {
                        "performance_id": self.musical_candidate.performance_id,
                        "rank": 1,
                        "reason": "관심 등록한 공연과 같은 장르입니다.",
                    }
                ],
            },
            {"id": "resp_test", "output_text": "{}"},
            "test-model",
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("recommendation_ai"),
            {"message": "이번 주 볼 공연 추천", "limit": 1},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["fallback_used"])
        self.assertEqual(response.data["summary"], "뮤지컬 선호를 바탕으로 추천했습니다.")
        self.assertEqual(response.data["results"][0]["performance"]["performance_id"], self.musical_candidate.performance_id)
        session = RecommendationSession.objects.get()
        self.assertEqual(session.provider, "openai")
        self.assertEqual(session.model_name, "test-model")
        self.assertEqual(session.validation_status, RecommendationSession.ValidationStatus.PASSED)

    @override_settings(OPENAI_API_SECRET_KEY="")
    def test_feedback_api_saves_feedback_for_session(self):
        self.client.force_authenticate(user=self.user)
        recommendation_response = self.client.post(
            reverse("recommendation_ai"),
            {"message": "추천해줘", "limit": 1},
            format="json",
        )
        session_id = recommendation_response.data["session_id"]

        response = self.client.post(
            reverse("recommendation_feedback", kwargs={"session_id": session_id}),
            {
                "performance_id": self.musical_candidate.performance_id,
                "feedback_type": RecommendationFeedback.FeedbackType.THUMBS_UP,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        feedback = RecommendationFeedback.objects.get()
        self.assertEqual(feedback.user, self.user)
        self.assertEqual(feedback.performance, self.musical_candidate)
        self.assertEqual(feedback.feedback_type, RecommendationFeedback.FeedbackType.THUMBS_UP)

        session = RecommendationSession.objects.get(pk=session_id)
        self.assertEqual(session.quality_score, 4)
        self.assertFalse(TrainingExampleCandidate.objects.exists())

    @override_settings(OPENAI_API_SECRET_KEY="")
    def test_feedback_api_rejects_performance_outside_session(self):
        self.client.force_authenticate(user=self.user)
        recommendation_response = self.client.post(
            reverse("recommendation_ai"),
            {"message": "뮤지컬 추천해줘", "limit": 1},
            format="json",
        )
        session_id = recommendation_response.data["session_id"]

        response = self.client.post(
            reverse("recommendation_feedback", kwargs={"session_id": session_id}),
            {
                "performance_id": self.liked_performance.performance_id,
                "feedback_type": RecommendationFeedback.FeedbackType.THUMBS_UP,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    @override_settings(OPENAI_API_SECRET_KEY="test-key", OPENAI_RECOMMENDATION_MODEL="test-model")
    @patch("apps.recommendations.services.request_openai_recommendations")
    def test_positive_feedback_creates_auto_approved_training_candidate(self, mock_openai):
        mock_openai.return_value = (
            {
                "summary": "친근하게 추천했어요.",
                "recommendations": [
                    {
                        "performance_id": self.musical_candidate.performance_id,
                        "rank": 1,
                        "reason": "뮤지컬 선호와 잘 맞아요.",
                    }
                ],
            },
            {"id": "resp_training", "output_text": "{}"},
            "test-model",
        )
        self.client.force_authenticate(user=self.user)
        recommendation_response = self.client.post(
            reverse("recommendation_ai"),
            {"message": "친근하게 공연 추천해줘", "limit": 1},
            format="json",
        )
        session_id = recommendation_response.data["session_id"]

        self.client.post(
            reverse("recommendation_feedback", kwargs={"session_id": session_id}),
            {
                "performance_id": self.musical_candidate.performance_id,
                "feedback_type": RecommendationFeedback.FeedbackType.BOOKING_LINK,
            },
            format="json",
        )

        session = RecommendationSession.objects.get(pk=session_id)
        self.assertEqual(session.quality_score, 8)
        candidate = TrainingExampleCandidate.objects.get(source_session=session)
        self.assertEqual(candidate.status, TrainingExampleCandidate.Status.AUTO_APPROVED)
        self.assertTrue(candidate.approved_for_training)
        self.assertEqual(candidate.input_payload["user_request"], "친근하게 공연 추천해줘")
        self.assertEqual(candidate.output_payload["summary"], "친근하게 추천했어요.")

    @override_settings(OPENAI_API_SECRET_KEY="test-key", OPENAI_RECOMMENDATION_MODEL="test-model")
    @patch("apps.recommendations.services.request_openai_recommendations")
    def test_blocking_negative_feedback_rejects_training_candidate(self, mock_openai):
        mock_openai.return_value = (
            {
                "summary": "추천 이유를 만들었습니다.",
                "recommendations": [
                    {
                        "performance_id": self.musical_candidate.performance_id,
                        "rank": 1,
                        "reason": "뮤지컬 선호와 잘 맞아요.",
                    }
                ],
            },
            {"id": "resp_negative", "output_text": "{}"},
            "test-model",
        )
        self.client.force_authenticate(user=self.user)
        recommendation_response = self.client.post(
            reverse("recommendation_ai"),
            {"message": "공연 추천", "limit": 1},
            format="json",
        )
        session_id = recommendation_response.data["session_id"]

        self.client.post(
            reverse("recommendation_feedback", kwargs={"session_id": session_id}),
            {"feedback_type": RecommendationFeedback.FeedbackType.REASON_NOT_HELPFUL},
            format="json",
        )

        candidate = TrainingExampleCandidate.objects.get(source_session_id=session_id)
        self.assertEqual(candidate.status, TrainingExampleCandidate.Status.REJECTED)
        self.assertFalse(candidate.approved_for_training)
        self.assertIn("blocking_negative_feedback", candidate.rejection_reasons)

    @override_settings(OPENAI_API_SECRET_KEY="test-key", OPENAI_RECOMMENDATION_MODEL="test-model")
    @patch("apps.recommendations.services.request_openai_recommendations")
    def test_export_recommendation_training_data_command_writes_jsonl(self, mock_openai):
        mock_openai.return_value = (
            {
                "summary": "추천했어요.",
                "recommendations": [
                    {
                        "performance_id": self.musical_candidate.performance_id,
                        "rank": 1,
                        "reason": "뮤지컬 선호와 잘 맞아요.",
                    }
                ],
            },
            {"id": "resp_export", "output_text": "{}"},
            "test-model",
        )
        self.client.force_authenticate(user=self.user)
        recommendation_response = self.client.post(
            reverse("recommendation_ai"),
            {"message": "공연 추천", "limit": 1},
            format="json",
        )
        self.client.post(
            reverse("recommendation_feedback", kwargs={"session_id": recommendation_response.data["session_id"]}),
            {"feedback_type": RecommendationFeedback.FeedbackType.BOOKING_LINK},
            format="json",
        )

        with TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "recommendation_sft.jsonl"
            call_command(
                "export_recommendation_training_data",
                "--format",
                "neutral",
                "--output",
                str(output_path),
            )
            lines = output_path.read_text(encoding="utf-8").splitlines()

        self.assertEqual(len(lines), 1)
        record = json.loads(lines[0])
        self.assertEqual(record["input"]["user_request"], "공연 추천")
        self.assertEqual(record["output"]["summary"], "추천했어요.")
