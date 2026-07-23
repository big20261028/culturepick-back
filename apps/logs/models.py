from django.db import models
from django.conf import settings


class SearchLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="search_logs"
    )
    keyword = models.CharField(max_length=255, blank=True)
    filter_region = models.CharField(max_length=100, blank=True)
    filter_genre = models.CharField(max_length=100, blank=True)
    filter_status = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "search_logs"
        indexes = [
            models.Index(fields=["created_at"], name="search_logs_created_idx"),
        ]


class ViewLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="view_logs"
    )
    performance_id = models.CharField(max_length=20)
    log_type = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "view_logs"
        indexes = [
            models.Index(fields=["created_at"], name="view_logs_created_idx"),
        ]


class QnALog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="qna_logs"
    )
    question = models.TextField()
    answer = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "qna_logs"
        indexes = [
            models.Index(fields=["created_at"], name="qna_logs_created_idx"),
        ]


class SearchLogDailyAggregate(models.Model):
    log_date = models.DateField()
    filter_region = models.CharField(max_length=100, blank=True)
    filter_genre = models.CharField(max_length=100, blank=True)
    filter_status = models.CharField(max_length=50, blank=True)
    count = models.PositiveBigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "search_log_daily_aggregates"
        constraints = [
            models.UniqueConstraint(
                fields=(
                    "log_date",
                    "filter_region",
                    "filter_genre",
                    "filter_status",
                ),
                name="unique_search_log_daily_bucket",
            ),
        ]


class ViewLogDailyAggregate(models.Model):
    log_date = models.DateField()
    performance_id = models.CharField(max_length=20)
    log_type = models.CharField(max_length=50, blank=True)
    count = models.PositiveBigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "view_log_daily_aggregates"
        constraints = [
            models.UniqueConstraint(
                fields=("log_date", "performance_id", "log_type"),
                name="unique_view_log_daily_bucket",
            ),
        ]


class QnALogDailyAggregate(models.Model):
    log_date = models.DateField(unique=True)
    count = models.PositiveBigIntegerField(default=0)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "qna_log_daily_aggregates"
