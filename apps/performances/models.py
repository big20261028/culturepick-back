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
    facility_characteristic = models.CharField(max_length=100, blank=True, help_text="시설특성 (fcltychartr)")
    sido = models.CharField(max_length=50, blank=True, help_text="시도명")
    gugun = models.CharField(max_length=50, blank=True, help_text="구군명")
    address = models.CharField(max_length=500, blank=True, help_text="주소")
    homepage_url = models.URLField(max_length=1000, blank=True, help_text="시설 홈페이지 (relateurl)")
    has_parking_lot = models.BooleanField(default=False, help_text="주차장 보유 여부 (parkinglot)")
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
    genre_code = models.CharField(max_length=10, blank=True, help_text="KOPIS 장르 코드 (shcate)")
    start_date = models.DateField(null=True, blank=True, help_text="공연시작일 (prfpdfrom)")
    end_date = models.DateField(null=True, blank=True, help_text="공연종료일 (prfpdto)")
    status = models.CharField(
        max_length=20,
        choices=Status.choices,
        default=Status.UPCOMMING,
        help_text="공연상태 (prfstate)",
    )
    status_code = models.CharField(max_length=10, blank=True, help_text="KOPIS 공연상태 코드")
    stage_id = models.CharField(max_length=20, blank=True, help_text="공연장 ID (mt13id)")
    facility_name = models.CharField(max_length=255, blank=True, help_text="공연시설명 원문 (fcltynm)")
    first_registered_at = models.DateTimeField(null=True, blank=True, help_text="KOPIS 최초 등록일 (frstregdt)")
    kopis_updated_at = models.DateTimeField(null=True, blank=True, help_text="KOPIS 최종 수정일 (updatedate)")
    cast = models.TextField(blank=True, help_text="출연진 (prfcast)")
    crew = models.TextField(blank=True, help_text="스태프 (prfcrew)")
    runtime = models.CharField(max_length=100, blank=True, help_text="공연런타임 (prfruntime)")
    age_rating = models.CharField(max_length=50, blank=True, help_text="관람등급 (prfage)")
    synopsis = models.TextField(blank=True, help_text="공연 줄거리/소개 (sty)")
    price_info = models.TextField(blank=True, help_text="티켓가격 (pcseguidance)")
    min_price = models.PositiveIntegerField(null=True, blank=True, help_text="파싱된 최저가")
    max_price = models.PositiveIntegerField(null=True, blank=True, help_text="파싱된 최고가")
    is_free = models.BooleanField(default=False, help_text="무료 공연 여부")
    price_parse_status = models.CharField(max_length=20, blank=True, help_text="가격 파싱 상태")
    schedule_info = models.TextField(blank=True, help_text="공연시간 (dtguidance)")
    openrun = models.BooleanField(default=False, help_text="오픈런 여부 (openrun)")
    is_visit = models.BooleanField(default=False, help_text="내한 여부 (visit)")
    is_child = models.BooleanField(default=False, help_text="아동 공연 여부 (child)")
    is_daehakro = models.BooleanField(default=False, help_text="대학로 공연 여부 (daehakro)")
    is_festival = models.BooleanField(default=False, help_text="축제 여부 (festival)")
    is_musical_license = models.BooleanField(default=False, help_text="라이선스 뮤지컬 여부 (musicallicense)")
    is_musical_create = models.BooleanField(default=False, help_text="창작 뮤지컬 여부 (musicalcreate)")
    production_company = models.CharField(max_length=255, blank=True, help_text="제작사 (entrpsnmP)")
    agency = models.CharField(max_length=255, blank=True, help_text="기획사 (entrpsnmA)")
    host = models.CharField(max_length=255, blank=True, help_text="주최 (entrpsnmH)")
    organizer = models.CharField(max_length=255, blank=True, help_text="주관 (entrpsnmS)")
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
            models.Index(fields=["genre_code"]),
            models.Index(fields=["status"]),
            models.Index(fields=["status_code"]),
            models.Index(fields=["start_date", "end_date"]),
            models.Index(fields=["min_price", "max_price"]),
            models.Index(fields=["is_child"]),
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


class PerformancePrice(models.Model):
    performance = models.ForeignKey(
        Performance,
        on_delete=models.CASCADE,
        related_name="price_options",
        help_text="공연 FK",
    )
    label = models.CharField(max_length=100, help_text="좌석/권종명")
    price = models.PositiveIntegerField(help_text="가격")
    currency = models.CharField(max_length=10, default="KRW", help_text="통화")
    raw_text = models.CharField(max_length=255, blank=True, help_text="파싱에 사용한 원문 조각")
    sort_order = models.PositiveSmallIntegerField(default=0, help_text="정렬 순서")

    class Meta:
        db_table = "performance_prices"
        ordering = ["sort_order", "id"]
        verbose_name = "공연 가격"
        verbose_name_plural = "공연 가격 목록"
        indexes = [
            models.Index(fields=["price"]),
            models.Index(fields=["label"]),
        ]

    def __str__(self):
        return f"{self.performance_id} - {self.label} {self.price}{self.currency}"


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
    
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name='performance_actions',
    )
    performance = models.ForeignKey(
        Performance,
        on_delete=models.CASCADE,
        related_name = 'users_performance_actions',
    )
    action_type = models.CharField(
        max_length=20,
        choices=ActionType.choices,
    )
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'users_performance_actions'
        unique_together = ('user', 'performance', 'action_type')

    def __str__(self):
        return f"{self.user} - {self.performance} - {self.action_type}"
