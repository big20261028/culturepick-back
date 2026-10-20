"""Audit reproduction only: passing means the documented defect was reproduced.

Explicitly run this module; it is not part of normal test discovery.
Uses synthetic records, a disposable PostgreSQL database, and mocked AI.
"""
from concurrent.futures import ThreadPoolExecutor
from threading import Barrier, local
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.db import close_old_connections, connection
from django.db.models.query import QuerySet
from django.test import TestCase, TransactionTestCase
from django.test.utils import CaptureQueriesContext
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APIClient

from apps.community.models import Post
from apps.performances.models import Performance, UsersPerformanceAction
from apps.recommendations.management.commands.export_recommendation_training_data import Command
from apps.recommendations.models import RecommendationSession, TrainingExampleCandidate
from apps.recommendations.services import (
    get_recommendation_candidates,
    record_feedback_and_update_quality,
)

User = get_user_model()


def make_user():
    return User.objects.create_user(email="audit-only@example.com", password="AuditOnly123!")


class DataProbes(TestCase):
    def test_public_author_email(self):
        user = make_user()
        post = Post.objects.create(author=user, title="Audit", content="<p>Audit</p>")
        response = APIClient().get(reverse("community_post_detail", args=[post.pk]))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.data["author_email"], user.email)
        self.assertEqual(response.data["author_display_name"], user.email)
        print("PROBE public_email: anonymous GET exposes email in two fields")

    def test_rejected_candidate_becomes_exportable_again(self):
        user = make_user()
        session = RecommendationSession.objects.create(
            user=user,
            provider="gms",
            validation_status="passed",
            candidate_snapshot=[{"performance_id": "AUDIT-P1"}],
            parsed_response={
                "summary": "Synthetic",
                "recommendations": [{"performance_id": "AUDIT-P1", "reason": "Synthetic"}],
            },
        )
        candidate = TrainingExampleCandidate.objects.create(
            source_session=session, status="rejected", approved_for_training=False,
            reviewed_by=user, reviewed_at=timezone.now(),
        )
        record_feedback_and_update_quality(
            session=session, user=user, feedback_type="booking_link"
        )
        candidate.refresh_from_db()
        self.assertEqual(candidate.status, "auto_approved")
        self.assertTrue(Command._approved_queryset(False).filter(pk=candidate.pk).exists())
        print("PROBE review_override: manually rejected candidate now selected for export")

    def test_repeated_clicks_inflate_quality(self):
        user = make_user()
        session = RecommendationSession.objects.create(
            user=user, provider="gms", validation_status="passed",
            candidate_snapshot=[{"performance_id": "AUDIT-P2"}],
            parsed_response={"recommendations": [{"performance_id": "AUDIT-P2"}]},
        )
        client = APIClient()
        client.force_authenticate(user)
        for _ in range(8):
            response = client.post(
                reverse("recommendation_feedback", args=[session.pk]),
                {"feedback_type": "click"}, format="json",
            )
            self.assertEqual(response.status_code, 201)
        session.refresh_from_db()
        self.assertEqual(session.quality_score, 8)
        self.assertEqual(session.feedback.count(), 8)
        print("PROBE repeated_clicks: 8 identical API events => score 8, auto_approved")

    def test_candidate_query_growth_with_warm_vectors(self):
        for index in range(20):
            Performance.objects.create(
                performance_id=f"AUDIT-{index}", title=f"Show {index}", genre_code="GGGA"
            )
        get_recommendation_candidates(pool_size=20)
        with CaptureQueriesContext(connection) as first:
            get_recommendation_candidates(pool_size=20)
        for index in range(20, 40):
            Performance.objects.create(
                performance_id=f"AUDIT-{index}", title=f"Show {index}", genre_code="GGGA"
            )
        get_recommendation_candidates(pool_size=40)
        with CaptureQueriesContext(connection) as second:
            get_recommendation_candidates(pool_size=40)
        self.assertGreaterEqual(len(second) - len(first), 20)
        print(f"PROBE warm_candidate_queries: 20={len(first)}, 40={len(second)}")


class RequestTransactionProbes(TransactionTestCase):
    def test_malformed_ai_response_leaves_session_after_500(self):
        user = make_user()
        Performance.objects.create(performance_id="AUDIT-ERR", title="Synthetic")
        client = APIClient()
        client.force_authenticate(user)
        with patch(
            "apps.recommendations.services.request_openai_recommendations",
            return_value=([], {}, "audit-mock"),
        ):
            response = client.post(
                reverse("recommendation_ai"), {"message": "Synthetic"}, format="json"
            )
        self.assertEqual(response.status_code, 500)
        self.assertEqual(RecommendationSession.objects.count(), 1)
        self.assertEqual(RecommendationSession.objects.get().validation_status, "not_run")
        print("PROBE partial_commit: HTTP 500 with 1 persisted incomplete recommendation session")

    def test_concurrent_interest_registration(self):
        user = make_user()
        performance = Performance.objects.create(performance_id="AUDIT-RACE", title="Synthetic")
        barrier = Barrier(2, timeout=15)
        thread_state = local()
        original_exists = QuerySet.exists

        def synchronized_exists(queryset):
            result = original_exists(queryset)
            if queryset.model is UsersPerformanceAction and not getattr(thread_state, "waited", False):
                thread_state.waited = True
                barrier.wait()
            return result

        def post_action(_):
            close_old_connections()
            try:
                client = APIClient()
                client.force_authenticate(User.objects.get(pk=user.pk))
                response = client.post(
                    reverse("performance_action", args=[performance.pk]),
                    {"action_type": "interest", "is_active": True}, format="json",
                )
                return response.status_code
            finally:
                close_old_connections()

        with patch.object(QuerySet, "exists", synchronized_exists):
            with ThreadPoolExecutor(max_workers=2) as executor:
                statuses = sorted(executor.map(post_action, range(2)))
        self.assertEqual(statuses, [200, 500])
        self.assertEqual(UsersPerformanceAction.objects.count(), 1)
        print(f"PROBE concurrent_interest: simultaneous identical requests => {statuses}")
