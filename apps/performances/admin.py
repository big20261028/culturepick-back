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
    list_display = ("venue_id", "name", "sido", "gugun", "seat_scale", "synced_at")
    search_fields = ("name", "sido", "gugun")


@admin.register(Performance)
class PerformanceAdmin(admin.ModelAdmin):
    list_display = ("performance_id", "title", "genre", "status", "start_date", "end_date", "view_count", "zzim_count")
    list_filter = ("genre", "status")
    search_fields = ("title", "cast")
    inlines = [PerformanceImageInline, BookingLinkInline]