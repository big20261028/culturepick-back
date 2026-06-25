from django.contrib.auth import get_user_model
from django.conf import settings
from django.core.management import call_command
from django.test import TestCase
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from unittest.mock import patch

from apps.performances.kopis.client import RawPerformanceDetail, RawVenueDetail
from apps.performances.kopis.client import GenreCode
from apps.performances.management.commands.sync_kopis import ALL_GENRES
from apps.performances.kopis.parser import parse_performance_detail
from apps.performances.kopis.sync import parse_price_info, parse_price_options, sync_performance, sync_venue
from apps.performances.models import (
    BookingLink,
    Performance,
    PerformanceImage,
    PerformancePrice,
    UsersPerformanceAction,
    Venue,
)
from apps.performances.utils.address import parse_sido_gugun
from apps.performances.tasks import ping_task, sync_kopis_task, sync_ongoing_performances, sync_upcoming_performances
from apps.performances.tasks import TARGET_GENRES

User = get_user_model()


class CeleryTaskTests(TestCase):
    def test_celery_redis_cluster_safe_defaults_are_configured(self):
        self.assertFalse(settings.CELERY_WORKER_ENABLE_REMOTE_CONTROL)
        self.assertEqual(
            settings.CELERY_BROKER_TRANSPORT_OPTIONS["global_keyprefix"],
            "{culturepick-celery}:",
        )

    def test_ping_task_returns_pong(self):
        result = ping_task()

        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["message"], "pong")
        self.assertIn("finished_at", result)

    @patch("apps.performances.tasks.call_command")
    def test_sync_kopis_task_wraps_management_command(self, mock_call_command):
        result = sync_kopis_task(
            stdate="20260701",
            eddate="20260702",
            genre="CCCA",
            with_venues=True,
        )

        mock_call_command.assert_called_once_with(
            "sync_kopis",
            stdate="20260701",
            eddate="20260702",
            genre="CCCA",
            with_venues=True,
        )
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["genre"], "CCCA")

    @patch("apps.performances.tasks._release_task_lock")
    @patch("apps.performances.tasks.sync_performances_in_range")
    @patch("apps.performances.tasks._date_range", return_value=("20260624", "20260724"))
    @patch("apps.performances.tasks._acquire_task_lock", return_value=(True, "lock-key", "token"))
    def test_sync_ongoing_uses_30_day_range_and_lock(
        self,
        mock_acquire,
        mock_date_range,
        mock_sync,
        mock_release,
    ):
        from apps.performances.kopis.sync import SyncResult

        mock_sync.return_value = SyncResult(created=1)

        result = sync_ongoing_performances()

        mock_acquire.assert_called_once_with("sync_ongoing_performances")
        mock_date_range.assert_called_once_with(days_before=0, days_after=30)
        self.assertEqual(mock_sync.call_count, len(TARGET_GENRES))
        mock_release.assert_called_once_with("sync_ongoing_performances", "lock-key", "token")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["days_after"], 30)

    @patch("apps.performances.tasks._release_task_lock")
    @patch("apps.performances.tasks.sync_performances_in_range")
    @patch("apps.performances.tasks._date_range", return_value=("20260624", "20260823"))
    @patch("apps.performances.tasks._acquire_task_lock", return_value=(True, "lock-key", "token"))
    def test_sync_upcoming_uses_60_day_range_and_lock(
        self,
        mock_acquire,
        mock_date_range,
        mock_sync,
        mock_release,
    ):
        from apps.performances.kopis.sync import SyncResult

        mock_sync.return_value = SyncResult(updated=1)

        result = sync_upcoming_performances()

        mock_acquire.assert_called_once_with("sync_upcoming_performances")
        mock_date_range.assert_called_once_with(days_before=0, days_after=60)
        self.assertEqual(mock_sync.call_count, len(TARGET_GENRES))
        mock_release.assert_called_once_with("sync_upcoming_performances", "lock-key", "token")
        self.assertEqual(result["status"], "ok")
        self.assertEqual(result["days_after"], 60)

    @patch("apps.performances.tasks.sync_performances_in_range")
    @patch("apps.performances.tasks._acquire_task_lock", return_value=(False, "lock-key", ""))
    def test_scheduled_sync_skips_when_lock_exists(self, mock_acquire, mock_sync):
        result = sync_ongoing_performances()

        mock_acquire.assert_called_once_with("sync_ongoing_performances")
        mock_sync.assert_not_called()
        self.assertEqual(result["status"], "skipped")
        self.assertEqual(result["reason"], "already_running")


class CeleryBeatScheduleCommandTests(TestCase):
    def test_setup_celery_beat_schedule_registers_kopis_tasks_only(self):
        from django_celery_beat.models import CrontabSchedule, PeriodicTask

        cleanup_schedule = CrontabSchedule.objects.create(
            minute="0",
            hour="4",
            day_of_week="*",
            day_of_month="*",
            month_of_year="*",
            timezone=settings.TIME_ZONE,
        )
        PeriodicTask.objects.create(
            name="celery.backend_cleanup",
            task="celery.backend_cleanup",
            crontab=cleanup_schedule,
            enabled=True,
        )

        call_command("setup_celery_beat_schedule")

        ongoing = PeriodicTask.objects.get(name="daily-sync-ongoing-performances")
        upcoming = PeriodicTask.objects.get(name="daily-sync-upcoming-performances")
        cleanup = PeriodicTask.objects.get(name="celery.backend_cleanup")

        self.assertEqual(ongoing.task, "apps.performances.tasks.sync_ongoing_performances")
        self.assertEqual(ongoing.crontab.hour, "4")
        self.assertEqual(ongoing.crontab.minute, "10")
        self.assertEqual(upcoming.task, "apps.performances.tasks.sync_upcoming_performances")
        self.assertEqual(upcoming.crontab.hour, "4")
        self.assertEqual(upcoming.crontab.minute, "30")
        self.assertEqual(cleanup.task, "celery.backend_cleanup")


class KopisGenreCollectionTests(TestCase):
    def test_default_sync_targets_include_korean_music(self):
        self.assertIn(GenreCode.KOREAN_MUSIC, ALL_GENRES)
        self.assertIn(GenreCode.KOREAN_MUSIC, TARGET_GENRES)


class VenueAddressParsingTests(TestCase):
    def test_parse_sido_gugun_supports_major_city_addresses(self):
        cases = [
            ("대전광역시 서구 둔산대로 135", ("대전광역시", "서구")),
            ("서울특별시 종로구 세종대로 175", ("서울특별시", "종로구")),
            ("부산광역시 해운대구 수영강변대로 120", ("부산광역시", "해운대구")),
            ("제주특별자치도 제주시 서광로 2길 24", ("제주특별자치도", "제주시")),
        ]

        for address, expected in cases:
            with self.subTest(address=address):
                self.assertEqual(parse_sido_gugun(address), expected)

    def test_parse_sido_gugun_keeps_first_city_for_nested_districts(self):
        self.assertEqual(
            parse_sido_gugun("경기도 성남시 분당구 성남대로 808"),
            ("경기도", "성남시"),
        )
        self.assertEqual(
            parse_sido_gugun("충청남도 천안시 동남구 성남면 1"),
            ("충청남도", "천안시"),
        )

    def test_parse_sido_gugun_handles_sejong_without_gugun(self):
        self.assertEqual(
            parse_sido_gugun("세종특별자치시 갈매로 387"),
            ("세종특별자치시", ""),
        )


class KopisPerformanceDetailTests(TestCase):
    def test_parse_performance_detail_reads_synopsis_from_sty(self):
        xml = b"""
        <dbs>
          <db>
            <mt20id>PF000001</mt20id>
            <prfnm>Test Performance</prfnm>
            <prfpdfrom>2026.01.01</prfpdfrom>
            <prfpdto>2026.01.31</prfpdto>
            <fcltynm>Test Venue</fcltynm>
            <mt10id></mt10id>
            <mt13id>STAGE001</mt13id>
            <frstregdt>2026-01-01 09:30:00</frstregdt>
            <prfcast>Actor A</prfcast>
            <prfcrew>Crew A</prfcrew>
            <prfruntime>100 minutes</prfruntime>
            <prfage>8+</prfage>
            <sty>This is the KOPIS synopsis.</sty>
            <pcseguidance>R 10000</pcseguidance>
            <entrpsnmP>Production A</entrpsnmP>
            <entrpsnmA>Agency A</entrpsnmA>
            <entrpsnmH>Host A</entrpsnmH>
            <entrpsnmS>Organizer A</entrpsnmS>
            <genrenm>Musical</genrenm>
            <prfstate>Performing</prfstate>
            <poster>https://example.com/poster.jpg</poster>
            <area>Seoul</area>
            <dtguidance>Tue-Fri 20:00</dtguidance>
            <openrun>Y</openrun>
            <child>Y</child>
            <festival>N</festival>
            <updatedate>2026-01-02 10:30:00</updatedate>
          </db>
        </dbs>
        """

        detail = parse_performance_detail(xml)

        self.assertIsNotNone(detail)
        self.assertEqual(detail.sty, "This is the KOPIS synopsis.")
        self.assertEqual(detail.mt13id, "STAGE001")
        self.assertEqual(detail.entrpsnmP, "Production A")
        self.assertEqual(detail.openrun, "Y")
        self.assertEqual(detail.child, "Y")
        self.assertEqual(detail.updatedate, "2026-01-02 10:30:00")

    def test_sync_performance_saves_synopsis(self):
        raw = RawPerformanceDetail(
            mt20id="PF000002",
            prfnm="Synced Performance",
            prfpdfrom="2026.02.01",
            prfpdto="2026.02.28",
            fcltynm="Test Venue",
            mt10id="",
            prfcast="Actor B",
            prfcrew="Crew B",
            prfruntime="90 minutes",
            prfage="All",
            sty="Stored synopsis from KOPIS.",
            pcseguidance="R석 150,000원, S석 100,000원",
            genrenm="뮤지컬",
            prfstate="공연예정",
            poster="https://example.com/poster2.jpg",
            area="Seoul",
            dtguidance="Sat 15:00",
            mt13id="STAGE002",
            frstregdt="2026-01-10 09:00:00",
            entrpsnmP="Production B",
            entrpsnmA="Agency B",
            entrpsnmH="Host B",
            entrpsnmS="Organizer B",
            openrun="Y",
            child="Y",
            festival="N",
            musicallicense="Y",
            updatedate="2026-01-11 10:00:00",
        )

        sync_performance(raw, client=None)

        performance = Performance.objects.get(performance_id="PF000002")
        self.assertEqual(performance.synopsis, "Stored synopsis from KOPIS.")
        self.assertEqual(performance.genre_code, "GGGA")
        self.assertEqual(performance.status_code, "01")
        self.assertEqual(performance.stage_id, "STAGE002")
        self.assertEqual(performance.min_price, 100000)
        self.assertEqual(performance.max_price, 150000)
        self.assertFalse(performance.is_free)
        self.assertEqual(performance.price_parse_status, "parsed")
        self.assertEqual(
            list(
                PerformancePrice.objects.filter(performance=performance)
                .order_by("sort_order")
                .values_list("label", "price")
            ),
            [("R석", 150000), ("S석", 100000)],
        )
        self.assertTrue(performance.openrun)
        self.assertTrue(performance.is_child)
        self.assertTrue(performance.is_musical_license)
        self.assertEqual(performance.production_company, "Production B")
        self.assertIsNotNone(performance.kopis_updated_at)

    def test_parse_price_info_handles_free_and_unknown_values(self):
        self.assertEqual(parse_price_info("무료"), (0, 0, True, "free"))
        self.assertEqual(parse_price_info("가격 미정"), (None, None, False, "unparsed"))

    def test_parse_price_options_splits_seat_prices(self):
        self.assertEqual(
            parse_price_options("R 150,000, S 100,000"),
            [
                {"label": "R", "price": 150000, "currency": "KRW", "raw_text": "R 150,000"},
                {"label": "S", "price": 100000, "currency": "KRW", "raw_text": "S 100,000"},
            ],
        )

    def test_sync_venue_saves_ai_candidate_fields(self):
        raw = RawVenueDetail(
            mt10id="FC000100",
            fcltynm="Venue With Parking",
            sidonm="서울",
            gugunnm="종로",
            adres="서울 종로구",
            la="37.1234567",
            lo="127.1234567",
            seatscale="500",
            fcltychartr="문예회관",
            relateurl="https://venue.example.com",
            parkinglot="Y",
        )

        sync_venue(raw)

        venue = Venue.objects.get(venue_id="FC000100")
        self.assertEqual(venue.facility_characteristic, "문예회관")
        self.assertEqual(venue.homepage_url, "https://venue.example.com")
        self.assertTrue(venue.has_parking_lot)

    def test_sync_venue_fills_region_from_address_when_kopis_region_is_empty(self):
        raw = RawVenueDetail(
            mt10id="FC000101",
            fcltynm="Daejeon Arts Center",
            sidonm="",
            gugunnm="",
            adres="대전광역시 서구 둔산대로 135",
            la="36.3504119",
            lo="127.3845475",
            seatscale="1000",
        )

        sync_venue(raw)

        venue = Venue.objects.get(venue_id="FC000101")
        self.assertEqual(venue.sido, "대전광역시")
        self.assertEqual(venue.gugun, "서구")

    def test_sync_venue_preserves_existing_region_values(self):
        Venue.objects.create(
            venue_id="FC000102",
            name="Existing Venue",
            sido="서울특별시",
            gugun="종로구",
            address="서울특별시 종로구",
        )
        raw = RawVenueDetail(
            mt10id="FC000102",
            fcltynm="Existing Venue Renamed",
            sidonm="부산광역시",
            gugunnm="해운대구",
            adres="부산광역시 해운대구 수영강변대로 120",
            la="35.0",
            lo="129.0",
            seatscale="800",
        )

        sync_venue(raw)

        venue = Venue.objects.get(venue_id="FC000102")
        self.assertEqual(venue.name, "Existing Venue Renamed")
        self.assertEqual(venue.sido, "서울특별시")
        self.assertEqual(venue.gugun, "종로구")


class PerformanceDetailAPITests(APITestCase):
    def setUp(self):
        self.venue = Venue.objects.create(
            venue_id="FC000001",
            name="Test Hall",
            sido="Seoul",
            gugun="Jongno",
            address="Seoul Jongno",
            latitude="37.1234567",
            longitude="127.1234567",
            seat_scale=1000,
        )
        self.performance = Performance.objects.create(
            performance_id="PFDETAIL1",
            title="Detail Performance",
            genre="Musical",
            start_date="2026-03-01",
            end_date="2026-03-31",
            status="Performing",
            cast="Actor A",
            crew="Crew A",
            runtime="100 minutes",
            age_rating="8+",
            synopsis="A detailed synopsis for the performance.",
            price_info="R 10000",
            schedule_info="Tue-Fri 20:00",
            poster_url="https://example.com/poster.jpg",
            venue=self.venue,
        )
        PerformanceImage.objects.create(
            performance=self.performance,
            image_url="https://example.com/image1.jpg",
            sort_order=1,
        )
        BookingLink.objects.create(
            performance=self.performance,
            site_name="Ticket Site",
            url="https://tickets.example.com",
        )
        PerformancePrice.objects.create(
            performance=self.performance,
            label="R",
            price=10000,
            raw_text="R 10000",
            sort_order=0,
        )

    def test_detail_api_returns_public_performance_data(self):
        response = self.client.get(
            reverse("performance_detail", kwargs={"performance_id": self.performance.performance_id})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["performance_id"], self.performance.performance_id)
        self.assertEqual(response.data["title"], "Detail Performance")
        self.assertEqual(response.data["synopsis"], "A detailed synopsis for the performance.")
        self.assertEqual(response.data["venue"]["venue_id"], self.venue.venue_id)
        self.assertEqual(response.data["venue"]["longitude"], "127.1234567")
        self.assertEqual(response.data["images"][0]["image_url"], "https://example.com/image1.jpg")
        self.assertEqual(response.data["price_options"][0]["label"], "R")
        self.assertEqual(response.data["price_options"][0]["price"], 10000)
        self.assertEqual(response.data["booking_links"][0]["site_name"], "Ticket Site")
        self.assertFalse(response.data["is_interested"])
        self.assertFalse(response.data["is_watchlisted"])

        self.performance.refresh_from_db()
        self.assertEqual(self.performance.view_count, 1)

    def test_detail_api_returns_user_action_flags_for_authenticated_user(self):
        user = User.objects.create_user(
            email="detail-user@example.com",
            password="ValidPass123!",
            nickname="detail-user",
        )
        UsersPerformanceAction.objects.create(
            user=user,
            performance=self.performance,
            action_type=UsersPerformanceAction.ActionType.INTEREST,
        )
        UsersPerformanceAction.objects.create(
            user=user,
            performance=self.performance,
            action_type=UsersPerformanceAction.ActionType.WATCHLIST,
        )
        self.client.force_authenticate(user=user)

        response = self.client.get(
            reverse("performance_detail", kwargs={"performance_id": self.performance.performance_id})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertTrue(response.data["is_interested"])
        self.assertTrue(response.data["is_watchlisted"])


class PerformanceActionAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="action-user@example.com",
            password="ValidPass123!",
            nickname="action-user",
        )
        self.venue = Venue.objects.create(
            venue_id="FCACTION1",
            name="Action Hall",
            sido="Seoul",
            gugun="Jongno",
        )
        self.performance = Performance.objects.create(
            performance_id="PFACTION1",
            title="Action Performance",
            genre="Musical",
            status="Performing",
            venue=self.venue,
        )
        self.url = reverse(
            "performance_action",
            kwargs={"performance_id": self.performance.performance_id},
        )

    def test_action_api_requires_authentication(self):
        response = self.client.post(self.url, {"action_type": "interest"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_interest_action_toggles_on_and_off_and_updates_count(self):
        self.client.force_authenticate(user=self.user)

        first_response = self.client.post(self.url, {"action_type": "interest"}, format="json")

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertTrue(first_response.data["is_active"])
        self.assertTrue(first_response.data["is_interested"])
        self.assertFalse(first_response.data["is_watchlisted"])
        self.assertEqual(first_response.data["zzim_count"], 1)
        self.assertTrue(
            UsersPerformanceAction.objects.filter(
                user=self.user,
                performance=self.performance,
                action_type=UsersPerformanceAction.ActionType.INTEREST,
            ).exists()
        )

        detail_response = self.client.get(
            reverse("performance_detail", kwargs={"performance_id": self.performance.performance_id})
        )
        self.assertTrue(detail_response.data["is_interested"])

        second_response = self.client.post(self.url, {"action_type": "interest"}, format="json")

        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        self.assertFalse(second_response.data["is_active"])
        self.assertFalse(second_response.data["is_interested"])
        self.assertEqual(second_response.data["zzim_count"], 0)

        self.performance.refresh_from_db()
        self.assertEqual(self.performance.zzim_count, 0)

    def test_watchlist_action_supports_explicit_state_without_duplicates(self):
        self.client.force_authenticate(user=self.user)

        first_response = self.client.post(
            self.url,
            {"action_type": "watchlist", "is_active": True},
            format="json",
        )
        second_response = self.client.post(
            self.url,
            {"action_type": "watchlist", "is_active": True},
            format="json",
        )
        off_response = self.client.post(
            self.url,
            {"action_type": "watchlist", "is_active": False},
            format="json",
        )

        self.assertEqual(first_response.status_code, status.HTTP_200_OK)
        self.assertEqual(second_response.status_code, status.HTTP_200_OK)
        self.assertEqual(off_response.status_code, status.HTTP_200_OK)
        self.assertTrue(first_response.data["is_watchlisted"])
        self.assertTrue(second_response.data["is_watchlisted"])
        self.assertFalse(off_response.data["is_watchlisted"])
        self.assertEqual(
            UsersPerformanceAction.objects.filter(
                user=self.user,
                performance=self.performance,
                action_type=UsersPerformanceAction.ActionType.WATCHLIST,
            ).count(),
            0,
        )

    def test_action_api_rejects_invalid_action_type(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(self.url, {"action_type": "like"}, format="json")

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)


class PerformanceListSearchAPITests(APITestCase):
    def setUp(self):
        self.keyword = "햄릿"
        hamlet_venue = Venue.objects.create(
            venue_id="FCSEARCH1",
            name="세종문화회관",
            sido="서울",
            gugun="종로구",
        )
        venue_match = Venue.objects.create(
            venue_id="FCSEARCH2",
            name="햄릿아트홀",
            sido="서울",
            gugun="강남구",
        )

        Performance.objects.create(
            performance_id="PFSEARCH_TITLE",
            title="햄릿",
            genre="연극",
            cast="Actor A",
            poster_url="https://example.com/title.jpg",
            venue=hamlet_venue,
        )
        Performance.objects.create(
            performance_id="PFSEARCH_CAST",
            title="리어왕",
            genre="연극",
            cast="햄릿 배우",
            poster_url="https://example.com/cast.jpg",
            venue=hamlet_venue,
        )
        Performance.objects.create(
            performance_id="PFSEARCH_VENUE",
            title="오셀로",
            genre="연극",
            cast="Actor B",
            poster_url="https://example.com/venue.jpg",
            venue=venue_match,
        )
        Performance.objects.create(
            performance_id="PFSEARCH_NONE",
            title="맥베스",
            genre="연극",
            cast="Actor C",
            poster_url="https://example.com/none.jpg",
            venue=hamlet_venue,
        )

    def test_integrated_keyword_search_orders_by_weighted_score(self):
        response = self.client.get(
            reverse("performance_list"),
            {"keyword": self.keyword, "pageNum": 1, "pageSize": 10},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pageNum"], 1)
        self.assertEqual(response.data["pageSize"], 10)
        self.assertEqual(response.data["total"], 3)

        results = response.data["searchData"]
        self.assertEqual([item["performance_id"] for item in results], [
            "PFSEARCH_TITLE",
            "PFSEARCH_CAST",
            "PFSEARCH_VENUE",
        ])
        self.assertEqual([item["search_score"] for item in results], [100, 60, 40])
        self.assertEqual(results[0]["venue"]["name"], "세종문화회관")

    def test_integrated_keyword_search_supports_pagination_aliases(self):
        response = self.client.get(
            reverse("performance_list"),
            {"keyword": self.keyword, "page": 2, "page_size": 2},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["pageNum"], 2)
        self.assertEqual(response.data["pageSize"], 2)
        self.assertEqual(response.data["total"], 3)
        self.assertEqual(len(response.data["searchData"]), 1)

    def test_integrated_keyword_search_returns_user_action_flags(self):
        user = User.objects.create_user(
            email="search-actions@example.com",
            password="ValidPass123!",
            nickname="search-actions",
        )
        title_match = Performance.objects.get(performance_id="PFSEARCH_TITLE")
        cast_match = Performance.objects.get(performance_id="PFSEARCH_CAST")
        UsersPerformanceAction.objects.create(
            user=user,
            performance=title_match,
            action_type=UsersPerformanceAction.ActionType.INTEREST,
        )
        UsersPerformanceAction.objects.create(
            user=user,
            performance=cast_match,
            action_type=UsersPerformanceAction.ActionType.WATCHLIST,
        )
        self.client.force_authenticate(user=user)

        response = self.client.get(
            reverse("performance_list"),
            {"keyword": self.keyword, "pageNum": 1, "pageSize": 10},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = {item["performance_id"]: item for item in response.data["searchData"]}
        self.assertTrue(results["PFSEARCH_TITLE"]["is_interested"])
        self.assertFalse(results["PFSEARCH_TITLE"]["is_watchlisted"])
        self.assertFalse(results["PFSEARCH_CAST"]["is_interested"])
        self.assertTrue(results["PFSEARCH_CAST"]["is_watchlisted"])
        self.assertFalse(results["PFSEARCH_VENUE"]["is_interested"])
        self.assertFalse(results["PFSEARCH_VENUE"]["is_watchlisted"])


class PerformanceFeatureFilterAPITests(APITestCase):
    def setUp(self):
        self.seoul_venue = Venue.objects.create(
            venue_id="FCFILTER1",
            name="Seoul Arts Center",
            sido="\uc11c\uc6b8",
            gugun="\uc11c\ucd08",
            address="\uc11c\uc6b8 \uc11c\ucd08\uad6c",
        )
        self.busan_venue = Venue.objects.create(
            venue_id="FCFILTER2",
            name="Busan Hall",
            sido="\ubd80\uc0b0",
            gugun="\ud574\uc6b4\ub300",
            address="\ubd80\uc0b0 \ud574\uc6b4\ub300\uad6c",
        )

        Performance.objects.create(
            performance_id="PFFILTER_MATCH",
            title="Alpha Musical",
            genre="\ubba4\uc9c0\uceec",
            genre_code="GGGA",
            status="\uacf5\uc5f0\uc608\uc815",
            start_date="2026-05-01",
            venue=self.seoul_venue,
        )
        Performance.objects.create(
            performance_id="PFFILTER_STATUS",
            title="Alpha Musical Now",
            genre="\ubba4\uc9c0\uceec",
            genre_code="GGGA",
            status="\uacf5\uc5f0\uc911",
            start_date="2026-03-01",
            venue=self.seoul_venue,
        )
        Performance.objects.create(
            performance_id="PFFILTER_GENRE",
            title="Alpha Concert",
            genre="\ub300\uc911\uc74c\uc545",
            genre_code="CCCD",
            status="\uacf5\uc5f0\uc608\uc815",
            start_date="2026-06-01",
            venue=self.seoul_venue,
        )
        Performance.objects.create(
            performance_id="PFFILTER_KOREAN_MUSIC",
            title="Alpha Korean Music",
            genre="\ud55c\uad6d\uc74c\uc545(\uad6d\uc545)",
            genre_code="CCCC",
            status="\uacf5\uc5f0\uc608\uc815",
            start_date="2026-07-01",
            venue=self.seoul_venue,
        )
        Performance.objects.create(
            performance_id="PFFILTER_REGION",
            title="Alpha Busan Musical",
            genre="\ubba4\uc9c0\uceec",
            genre_code="GGGA",
            status="\uacf5\uc5f0\uc608\uc815",
            start_date="2026-04-01",
            venue=self.busan_venue,
        )

    def test_feature_search_filters_genre_region_status_and_keyword_together(self):
        response = self.client.get(
            reverse("performance_list"),
            {
                "genre": "musical",
                "local": "seoul",
                "status": "upcomming",
                "keyword": "Alpha",
                "pageNum": 1,
                "pageSize": 10,
                "sorted": "latest",
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(response.data["searchData"][0]["performance_id"], "PFFILTER_MATCH")
        self.assertEqual(response.data["searchData"][0]["search_score"], 0)

    def test_feature_search_supports_frontend_aliases_and_latest_sort(self):
        response = self.client.get(
            reverse("performance_list"),
            {
                "genre": "musical",
                "region": "busan",
                "sort": "latest",
                "page": 1,
                "page_size": 10,
            },
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(response.data["searchData"][0]["performance_id"], "PFFILTER_REGION")

    def test_feature_search_returns_user_action_flags(self):
        user = User.objects.create_user(
            email="feature-actions@example.com",
            password="ValidPass123!",
            nickname="feature-actions",
        )
        match = Performance.objects.get(performance_id="PFFILTER_MATCH")
        status_match = Performance.objects.get(performance_id="PFFILTER_STATUS")
        UsersPerformanceAction.objects.create(
            user=user,
            performance=match,
            action_type=UsersPerformanceAction.ActionType.INTEREST,
        )
        UsersPerformanceAction.objects.create(
            user=user,
            performance=status_match,
            action_type=UsersPerformanceAction.ActionType.WATCHLIST,
        )
        self.client.force_authenticate(user=user)

        response = self.client.get(
            reverse("performance_list"),
            {"genre": "musical", "pageNum": 1, "pageSize": 10},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        results = {item["performance_id"]: item for item in response.data["searchData"]}
        self.assertTrue(results["PFFILTER_MATCH"]["is_interested"])
        self.assertFalse(results["PFFILTER_MATCH"]["is_watchlisted"])
        self.assertFalse(results["PFFILTER_STATUS"]["is_interested"])
        self.assertTrue(results["PFFILTER_STATUS"]["is_watchlisted"])
        self.assertFalse(results["PFFILTER_REGION"]["is_interested"])
        self.assertFalse(results["PFFILTER_REGION"]["is_watchlisted"])

    def test_feature_search_genre_page_defaults_to_newest_start_date(self):
        response = self.client.get(
            reverse("performance_list"),
            {"genre": "musical", "pageNum": 1, "pageSize": 10},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(
            [item["performance_id"] for item in response.data["searchData"]],
            ["PFFILTER_MATCH", "PFFILTER_REGION", "PFFILTER_STATUS"],
        )

    def test_feature_search_supports_kopis_genre_code(self):
        response = self.client.get(
            reverse("performance_list"),
            {"genre": "GGGA", "pageNum": 1, "pageSize": 10},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total"], 3)
        self.assertEqual(
            [item["performance_id"] for item in response.data["searchData"]],
            ["PFFILTER_MATCH", "PFFILTER_REGION", "PFFILTER_STATUS"],
        )

    def test_feature_search_supports_korean_music_alias_and_code(self):
        for genre in ("koreanMusic", "CCCC", "cccc"):
            with self.subTest(genre=genre):
                response = self.client.get(
                    reverse("performance_list"),
                    {"genre": genre, "pageNum": 1, "pageSize": 10},
                )

                self.assertEqual(response.status_code, status.HTTP_200_OK)
                self.assertEqual(response.data["total"], 1)
                self.assertEqual(
                    response.data["searchData"][0]["performance_id"],
                    "PFFILTER_KOREAN_MUSIC",
                )
