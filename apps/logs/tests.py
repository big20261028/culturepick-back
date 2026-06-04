from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase

from apps.logs.models import QnALog, SearchLog, ViewLog
from apps.performances.models import Performance, UsersPerformanceAction, Venue

User = get_user_model()


class LogCreateAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="log-user@example.com",
            password="ValidPass123!",
            nickname="log-user",
        )
        self.venue = Venue.objects.create(
            venue_id="FCLOG1",
            name="Log Hall",
            sido="Seoul",
            gugun="Jongno",
        )
        self.performance = Performance.objects.create(
            performance_id="PFLOG1",
            title="Log Performance",
            genre="Musical",
            status="Performing",
            venue=self.venue,
        )

    def test_search_log_api_creates_anonymous_log(self):
        response = self.client.post(
            reverse("log_search"),
            {
                "keyword": "hamlet",
                "filter_region": "seoul",
                "filter_genre": "play",
                "filter_status": "performing",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        log = SearchLog.objects.get()
        self.assertIsNone(log.user)
        self.assertEqual(log.keyword, "hamlet")
        self.assertEqual(log.filter_region, "seoul")
        self.assertEqual(log.filter_genre, "play")
        self.assertEqual(log.filter_status, "performing")

    def test_view_log_api_attaches_authenticated_user(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("log_view"),
            {
                "performance_id": self.performance.performance_id,
                "log_type": "detail",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        log = ViewLog.objects.get()
        self.assertEqual(log.user, self.user)
        self.assertEqual(log.performance_id, self.performance.performance_id)
        self.assertEqual(log.log_type, "detail")

    def test_qna_log_api_saves_question_and_answer(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("log_qna"),
            {
                "question": "Recommend a musical",
                "answer": "Try Log Performance.",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        log = QnALog.objects.get()
        self.assertEqual(log.user, self.user)
        self.assertEqual(log.question, "Recommend a musical")
        self.assertEqual(log.answer, "Try Log Performance.")


class AutomaticLogTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="auto-log-user@example.com",
            password="ValidPass123!",
            nickname="auto-log-user",
        )
        self.venue = Venue.objects.create(
            venue_id="FCAUTOLOG1",
            name="Auto Log Hall",
            sido="Seoul",
            gugun="Jongno",
        )
        self.performance = Performance.objects.create(
            performance_id="PFAUTOLOG1",
            title="Auto Log Performance",
            genre="Musical",
            status="Performing",
            venue=self.venue,
        )
        self.second_performance = Performance.objects.create(
            performance_id="PFAUTOLOG2",
            title="Auto Log Performance Encore",
            genre="Musical",
            status="Performing",
            venue=self.venue,
        )

    def test_performance_search_records_first_page_search_log_only(self):
        response = self.client.get(
            reverse("performance_list"),
            {"keyword": "Auto", "pageNum": 1, "pageSize": 1},
        )
        second_page_response = self.client.get(
            reverse("performance_list"),
            {"keyword": "Auto", "pageNum": 2, "pageSize": 1},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_page_response.status_code, status.HTTP_200_OK)
        self.assertEqual(SearchLog.objects.count(), 1)
        log = SearchLog.objects.get()
        self.assertEqual(log.keyword, "Auto")

    def test_plain_performance_list_does_not_record_search_log(self):
        response = self.client.get(reverse("performance_list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertFalse(SearchLog.objects.exists())

    def test_performance_detail_records_view_log(self):
        response = self.client.get(
            reverse("performance_detail", kwargs={"performance_id": self.performance.performance_id})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        log = ViewLog.objects.get()
        self.assertIsNone(log.user)
        self.assertEqual(log.performance_id, self.performance.performance_id)
        self.assertEqual(log.log_type, "detail")

    def test_performance_action_records_interest_log(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("performance_action", kwargs={"performance_id": self.performance.performance_id}),
            {"action_type": UsersPerformanceAction.ActionType.INTEREST},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        log = ViewLog.objects.get()
        self.assertEqual(log.user, self.user)
        self.assertEqual(log.performance_id, self.performance.performance_id)
        self.assertEqual(log.log_type, "interest_on")
