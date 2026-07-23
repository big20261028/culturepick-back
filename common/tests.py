from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse


class HealthCheckTests(TestCase):
    def test_liveness_check_is_always_available(self):
        response = self.client.get(reverse("health_check"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    @patch("common.views._check_redis")
    @patch("common.views._check_database")
    def test_readiness_check_reports_healthy_dependencies(self, mock_database, mock_redis):
        response = self.client.get(reverse("readiness_check"))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.json(),
            {"status": "ok", "checks": {"database": "ok", "redis": "ok"}},
        )
        mock_database.assert_called_once_with()
        mock_redis.assert_called_once_with()

    @patch("common.views._check_redis", side_effect=OSError)
    @patch("common.views._check_database")
    def test_readiness_check_returns_service_unavailable_when_redis_is_down(self, mock_database, mock_redis):
        response = self.client.get(reverse("readiness_check"))

        self.assertEqual(response.status_code, 503)
        self.assertEqual(
            response.json(),
            {"status": "unavailable", "checks": {"database": "ok", "redis": "unavailable"}},
        )
        mock_database.assert_called_once_with()
        mock_redis.assert_called_once_with()
