from django.db import models
from django.utils import timezone


class Venue(models.Model):
    """공연시설 - KOPIS prfplc API"""

    venue_id = models.CharField(
        max_length=20,
        primary_key=True,
        help_text="KOPIS 공연시설 ID (mt10id)",
    )
    name = models.CharField(max_length=255, help_text="공연시설명")
    sido = models.CharField(max_length=50, blank=True, help_text="시도명")
    gugun = models.CharField(max_length=50, blank=True, help_text="구군명")
    address = models.CharField(max_length=500, blank=True, help_text="주소")
    latitude = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True, help_text="위도"
    )
    longitude = models.DecimalField(
        max_digits=10, decimal_places=7, null=True, blank=True, help_text="경도"
    )
    seat_scale = models.IntegerField(null=True, blank=True, help_text="좌석규모")
    synced_at = models.DateTimeField(default=timezone.now, help_text="KOPIS 마지막 동기화 시각")

    class Meta:
        db_table = "venues"
        verbose_name = "공연시설"
        verbose_name_plural = "공연시설 목록"

    def __str__(self):
        return f"{self.name} ({self.venue_id})"


class Performance(models.Model):
    """공연 - KOPIS pblprfr API"""

    class Status(models.TextChoices):
        UPCOMMING = "공연예정", "upcomming"
        PERFORMING = "공연중", "performing"
        DONE = "공연완료", "done"

    performance_id = models.CharField(
        max_length=20,
        primary_key=True,
        help_text="KOPIS 공연 ID (mt20id)",
    )
    title = models.CharField(max_length=500, help_text="공연명 (prfnm)")
    genre = models.CharField(max_length=100, blank=True, help_text="장르 (genrenm)")
    start_date = models.DateField(null=True, blank=True, help_text="공연시작일 (prfpdfrom)")
    end_date = models.DateField(null=True, blank=True, help_text="공연종료일 (prfpdto)")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.UPCOMING,
        help_text="공연상태 (prfstate)",
    )
    cast = models.TextField(blank=True, help_text="출연진 (prfcast)")
    crew = models.TextField(blank=True, help_text="스태프 (prfcrew)")
    runtime = models.CharField(max_length=100, blank=True, help_text="공연런타임 (prfruntime)")
    age_rating = models.CharField(max_length=50, blank=True, help_text="관람등급 (prfage)")
    price_info = models.TextField(blank=True, help_text="티켓가격 (pcseguidance)")
    schedule_info = models.TextField(blank=True, help_text="공연시간 (dtguidance)")
    poster_url = models.URLField(max_length=1000, blank=True, help_text="포스터 이미지 URL")
    venue = models.ForeignKey(
        Venue,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="performances",
        help_text="공연시설 FK",
    )
    view_count = models.IntegerField(default=0, help_text="누적 조회수")
    zzim_count = models.IntegerField(default=0, help_text="누적 관심저장수")
    synced_at = models.DateTimeField(default=timezone.now, help_text="KOPIS 마지막 동기화 시각")

    class Meta:
        db_table = "performances"
        verbose_name = "공연"
        verbose_name_plural = "공연 목록"
        indexes = [
            models.Index(fields=["genre"]),
            models.Index(fields=["status"]),
            models.Index(fields=["start_date", "end_date"]),
        ]

    def __str__(self):
        return f"{self.title} ({self.performance_id})"


class PerformanceImage(models.Model):
    """공연 소개 이미지 - KOPIS styurls (다중)"""

    performance = models.ForeignKey(
        Performance,
        on_delete=models.CASCADE,
        related_name="images",
        help_text="공연 FK",
    )
    image_url = models.URLField(max_length=1000, help_text="소개 이미지 URL")
    sort_order = models.PositiveSmallIntegerField(default=0, help_text="정렬 순서")

    class Meta:
        db_table = "performance_images"
        ordering = ["sort_order"]
        verbose_name = "공연 소개 이미지"

    def __str__(self):
        return f"{self.performance_id} - image {self.sort_order}"


class BookingLink(models.Model):
    """예매 링크 - KOPIS relates (다중 예매처)"""

    performance = models.ForeignKey(
        Performance,
        on_delete=models.CASCADE,
        related_name="booking_links",
        help_text="공연 FK",
    )
    site_name = models.CharField(max_length=100, help_text="예매처명 (relatenm)")
    url = models.URLField(max_length=1000, help_text="예매 URL (relateurl)")

    class Meta:
        db_table = "booking_links"
        verbose_name = "예매 링크"

    def __str__(self):
        return f"{self.performance_id} - {self.site_name}"

from django.conf import settings

class UsersPerformanceAction(models.Model):

    class ActionType(models.TextChoices):
        INTEREST = 'interest', '관심저장'
        WATCHLIST = 'watchlist', '볼예정'