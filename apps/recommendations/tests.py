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

from apps.performances.models import Performance, PerformancePrice, UsersPerformanceAction, Venue

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
        self.family_candidate = Performance.objects.create(
            performance_id="PFREC-FAMILY",
            title="Family Magic Musical",
            genre="Musical",
            genre_code="GGGA",
            start_date=today + timedelta(days=2),
            end_date=today + timedelta(days=25),
            status="Upcoming",
            min_price=20000,
            max_price=80000,
            age_rating="전체 관람가",
            synopsis="가족과 아이가 함께 보기 좋은 따뜻한 마술 뮤지컬입니다.",
            is_child=True,
            venue=self.venue,
        )
        PerformancePrice.objects.create(
            performance=self.family_candidate,
            label="R",
            price=80000,
            sort_order=1,
        )
        self.expensive_candidate = Performance.objects.create(
            performance_id="PFREC-EXPENSIVE",
            title="Premium Concert",
            genre="Concert",
            genre_code="CCCD",
            start_date=today + timedelta(days=4),
            end_date=today + timedelta(days=20),
            status="Upcoming",
            min_price=150000,
            max_price=220000,
            synopsis="화려하고 강렬한 프리미엄 콘서트입니다.",
            zzim_count=50,
            view_count=100,
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

    def test_candidate_scoring_uses_family_and_budget_intent(self):
        profile, candidates = get_recommendation_candidates(
            user=self.user,
            message="가족과 함께 볼 수 있는 10만원 이하 공연 추천",
            limit=5,
        )

        self.assertIn("family", profile["request_intent"]["features"])
        self.assertEqual(profile["request_intent"]["price"]["max_price"], 100000)
        self.assertEqual(candidates[0].performance, self.family_candidate)

    def test_demo_intent_handles_plain_korean_family_prompt(self):
        profile, candidates = get_recommendation_candidates(
            user=self.user,
            message="\uac00\uc871\uacfc \ubcf4\uae30 \uc88b\uc740 \uacf5\uc5f0 \ucd94\ucc9c\ud574\uc918",
            limit=5,
        )

        self.assertIn("demo", profile["request_intent"])
        self.assertIn("family", profile["request_intent"]["features"])
        self.assertEqual(candidates[0].performance, self.family_candidate)

    def test_demo_intent_handles_short_runtime_prompt(self):
        today = timezone.localdate()
        short_candidate = Performance.objects.create(
            performance_id="PFREC-SHORT",
            title="\uc9e7\uace0 \uac00\ubcbc\uc6b4 \uc5f0\uadf9",
            genre="Play",
            genre_code="AAAA",
            start_date=today + timedelta(days=6),
            end_date=today + timedelta(days=28),
            status="Upcoming",
            min_price=25000,
            max_price=50000,
            runtime="70\ubd84",
            synopsis="\ud1f4\uadfc \ud6c4\uc5d0\ub3c4 \ubd80\ub2f4 \uc5c6\uc774 \ubcf4\uae30 \uc88b\uc740 \uc9e7\uc740 \uacf5\uc5f0\uc785\ub2c8\ub2e4.",
            venue=self.venue,
        )
        Performance.objects.create(
            performance_id="PFREC-LONG",
            title="\uae34 \ub300\uc791 \ubba4\uc9c0\uceec",
            genre="Musical",
            genre_code="GGGA",
            start_date=today + timedelta(days=7),
            end_date=today + timedelta(days=28),
            status="Upcoming",
            min_price=30000,
            max_price=90000,
            runtime="180\ubd84",
            zzim_count=80,
            view_count=120,
            venue=self.venue,
        )

        profile, candidates = get_recommendation_candidates(
            user=self.user,
            message="\uc2dc\uac04 \uc5c6\uc744 \ub54c \ubcf4\uae30 \uc88b\uc740 \uacf5\uc5f0 \ucd94\ucc9c\ud574\uc918",
            limit=5,
        )

        self.assertIn("short_runtime", profile["request_intent"]["features"])
        self.assertEqual(candidates[0].performance, short_candidate)
        self.assertNotEqual(candidates[0].performance, self.expensive_candidate)
        self.assertTrue(any(item["key"].startswith("demo:") for item in candidates[0].contributions))
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
    def test_ai_recommendation_fallback_includes_constraint_notes(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("recommendation_ai"),
            {"message": "청각장애인과 함께 갈만한 공연", "limit": 1},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["fallback_used"])
        self.assertIn("constraint_notes", response.data)
        self.assertTrue(response.data["constraint_notes"])
        self.assertIn("전용 필드", response.data["summary"])
        self.assertIn("전용 필드", response.data["recommendations"][0]["reason"])

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

    @override_settings(
        AI_RECOMMENDATION_PROVIDER="gms",
        GMS_API_KEY="test-gms-key",
        GMS_RECOMMENDATION_MODEL="gpt-4.1",
    )
    @patch("apps.recommendations.services.request_openai_recommendations")
    def test_ai_recommendation_saves_gms_provider_response(self, mock_openai):
        mock_openai.return_value = (
            {
                "summary": "GMS瑜? ?ъ슜?댁꽌 異붿쿇?덉뒿?덈떎.",
                "recommendations": [
                    {
                        "performance_id": self.musical_candidate.performance_id,
                        "rank": 1,
                        "reason": "?붿껌 議곌굔怨?媛源뚯슫 怨듭뿰?낅땲??",
                    }
                ],
            },
            {"provider": "gms", "id": "resp_gms", "output_text": "{}"},
            "gpt-4.1",
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("recommendation_ai"),
            {"message": "媛議깃낵 蹂닿린 醫뗭? 怨듭뿰 異붿쿇", "limit": 1},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["fallback_used"])
        session = RecommendationSession.objects.get()
        self.assertEqual(session.provider, "gms")
        self.assertEqual(session.model_name, "gpt-4.1")
        self.assertEqual(session.validation_status, RecommendationSession.ValidationStatus.PASSED)

        self.client.post(
            reverse("recommendation_feedback", kwargs={"session_id": session.id}),
            {
                "performance_id": self.musical_candidate.performance_id,
                "feedback_type": RecommendationFeedback.FeedbackType.BOOKING_LINK,
            },
            format="json",
        )
        candidate = TrainingExampleCandidate.objects.get(source_session=session)
        self.assertEqual(candidate.status, TrainingExampleCandidate.Status.AUTO_APPROVED)
        self.assertTrue(candidate.approved_for_training)

    @override_settings(OPENAI_API_SECRET_KEY="test-key", OPENAI_RECOMMENDATION_MODEL="test-model")
    @patch("apps.recommendations.services.request_openai_recommendations")
    def test_ai_recommendation_uses_previous_session_context(self, mock_openai):
        previous_session = RecommendationSession.objects.create(
            user=self.user,
            request_text="뮤지컬 추천해줘",
            provider="openai",
            parsed_response={"summary": "뮤지컬을 추천했어요."},
            validation_status=RecommendationSession.ValidationStatus.PASSED,
        )
        RecommendationItem.objects.create(
            session=previous_session,
            performance=self.musical_candidate,
            rank=1,
            score=3.0,
            reason="이전에 추천한 공연입니다.",
            source=RecommendationItem.Source.OPENAI,
        )
        mock_openai.return_value = (
            {
                "summary": "이전 추천과 겹치지 않게 골랐어요.",
                "recommendations": [
                    {
                        "performance_id": self.family_candidate.performance_id,
                        "rank": 1,
                        "reason": "이전 추천을 제외하고 가족 관람 조건에 맞는 공연으로 골랐어요. 10만원 이하 좌석이 있고 전체 관람가라 함께 보기 좋습니다.",
                    }
                ],
            },
            {"id": "resp_context", "output_text": "{}"},
            "test-model",
        )
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("recommendation_ai"),
            {
                "message": "아까 말한 공연 말고 가족끼리 볼 공연 추천해줘",
                "limit": 1,
                "session_id": previous_session.id,
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(response.data["fallback_used"])
        called_kwargs = mock_openai.call_args.kwargs
        candidate_ids = [candidate["performance_id"] for candidate in called_kwargs["candidates"]]
        self.assertNotIn(self.musical_candidate.performance_id, candidate_ids)
        self.assertEqual(
            called_kwargs["profile_snapshot"]["conversation_context"]["session_id"],
            previous_session.id,
        )

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
