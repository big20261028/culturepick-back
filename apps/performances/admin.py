from django.contrib import admin
from .models import BookingLink, Performance, PerformanceImage, Venue


class PerformanceImageInline(admin.TabularInline):
    model = PerformanceImage
    extra = 0


class BookingLinkInline(admin.TabularInline):
    model = BookingLink
    extra = 0


@admin.register(Venue)
class VenueAdmin(admin.ModelAdmin):
    list_display = (
        "venue_id",
        "name",
        "sido",
        "gugun",
        "facility_characteristic",
        "seat_scale",
        "has_parking_lot",
        "synced_at",
    )
    list_filter = ("sido", "facility_characteristic", "has_parking_lot")
    search_fields = ("name", "sido", "gugun", "address")


@admin.register(Performance)
class PerformanceAdmin(admin.ModelAdmin):
    list_display = (
        "performance_id",
        "title",
        "genre",
        "genre_code",
        "status",
        "status_code",
        "start_date",
        "end_date",
        "min_price",
        "max_price",
        "is_child",
        "view_count",
        "zzim_count",
    )
    list_filter = ("genre", "genre_code", "status", "status_code", "is_free", "is_child", "is_festival")
    search_fields = ("title", "cast", "facility_name", "venue__name")
    inlines = [PerformanceImageInline, BookingLinkInline]
