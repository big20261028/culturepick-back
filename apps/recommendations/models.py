from django.conf import settings
from django.db import models

from apps.performances.models import Performance


class UserPreferenceProfile(models.Model):
    user = models.OneToOneField(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="recommendation_profile",
    )
    vector_data = models.JSONField(default=dict, blank=True)
    source_summary = models.JSONField(default=dict, blank=True)
    last_built_at = models.DateTimeField(null=True, blank=True)
    is_stale = models.BooleanField(default=True)
    version = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "recommendation_user_profiles"

    def __str__(self):
        return f"profile:{self.user_id}"


class PerformanceVector(models.Model):
    performance = models.OneToOneField(
        Performance,
        on_delete=models.CASCADE,
        related_name="recommendation_vector",
    )
    vector_data = models.JSONField(default=dict, blank=True)
    source_summary = models.JSONField(default=dict, blank=True)
    version = models.PositiveIntegerField(default=1)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "recommendation_performance_vectors"

    def __str__(self):
        return f"vector:{self.performance_id}"


class RecommendationSession(models.Model):
    class ValidationStatus(models.TextChoices):
        NOT_RUN = "not_run", "not_run"
        PASSED = "passed", "passed"
        FAILED = "failed", "failed"
        FALLBACK = "fallback", "fallback"

    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recommendation_sessions",
    )
    request_text = models.TextField(blank=True)
    provider = models.CharField(max_length=50, default="rule_based")
    model_name = models.CharField(max_length=100, blank=True)
    prompt_version = models.CharField(max_length=50, default="recommendation-v1")
    user_profile_snapshot = models.JSONField(default=dict, blank=True)
    candidate_snapshot = models.JSONField(default=list, blank=True)
    raw_response = models.JSONField(default=dict, blank=True)
    parsed_response = models.JSONField(default=dict, blank=True)
    validation_status = models.CharField(
        max_length=20,
        choices=ValidationStatus.choices,
        default=ValidationStatus.NOT_RUN,
    )
    fallback_used = models.BooleanField(default=False)
    quality_score = models.FloatField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "recommendation_sessions"
        ordering = ["-created_at"]

    def __str__(self):
        return f"recommendation_session:{self.pk}"


class RecommendationItem(models.Model):
    class Source(models.TextChoices):
        OPENAI = "openai", "openai"
        CANDIDATE = "candidate", "candidate"
        FALLBACK = "fallback", "fallback"

    session = models.ForeignKey(
        RecommendationSession,
        on_delete=models.CASCADE,
        related_name="items",
    )
    performance = models.ForeignKey(
        Performance,
        on_delete=models.CASCADE,
        related_name="recommendation_items",
    )
    rank = models.PositiveIntegerField()
    score = models.FloatField(default=0)
    reason = models.TextField(blank=True)
    source = models.CharField(max_length=20, choices=Source.choices, default=Source.CANDIDATE)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "recommendation_items"
        ordering = ["rank", "id"]
        unique_together = ("session", "performance")

    def __str__(self):
        return f"{self.session_id}:{self.performance_id}:{self.rank}"


class RecommendationFeedback(models.Model):
    class FeedbackType(models.TextChoices):
        CLICK = "click", "click"
        INTEREST = "interest", "interest"
        WATCHLIST = "watchlist", "watchlist"
        BOOKING_LINK = "booking_link", "booking_link"
        THUMBS_UP = "thumbs_up", "thumbs_up"
        THUMBS_DOWN = "thumbs_down", "thumbs_down"
        REGENERATE = "regenerate", "regenerate"
        REASON_NOT_HELPFUL = "reason_not_helpful", "reason_not_helpful"
        NOT_MY_TASTE = "not_my_taste", "not_my_taste"
        ALREADY_SEEN = "already_seen", "already_seen"

    session = models.ForeignKey(
        RecommendationSession,
        on_delete=models.CASCADE,
        related_name="feedback",
    )
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recommendation_feedback",
    )
    performance = models.ForeignKey(
        Performance,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="recommendation_feedback",
    )
    feedback_type = models.CharField(max_length=30, choices=FeedbackType.choices)
    metadata = models.JSONField(default=dict, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "recommendation_feedback"
        ordering = ["-created_at"]

    def __str__(self):
        return f"feedback:{self.session_id}:{self.feedback_type}"


class TrainingExampleCandidate(models.Model):
    class Status(models.TextChoices):
        AUTO_APPROVED = "auto_approved", "auto_approved"
        NEEDS_REVIEW = "needs_review", "needs_review"
        REJECTED = "rejected", "rejected"
        EXPORTED = "exported", "exported"

    class TrainingTask(models.TextChoices):
        RECOMMENDATION_REASONING = "recommendation_reasoning", "recommendation_reasoning"
        QUERY_UNDERSTANDING = "query_understanding", "query_understanding"

    source_session = models.OneToOneField(
        RecommendationSession,
        on_delete=models.CASCADE,
        related_name="training_candidate",
    )
    status = models.CharField(max_length=30, choices=Status.choices, default=Status.NEEDS_REVIEW)
    training_task = models.CharField(
        max_length=50,
        choices=TrainingTask.choices,
        default=TrainingTask.RECOMMENDATION_REASONING,
    )
    input_payload = models.JSONField(default=dict, blank=True)
    output_payload = models.JSONField(default=dict, blank=True)
    chosen_output = models.JSONField(default=dict, blank=True)
    rejected_output = models.JSONField(default=dict, blank=True)
    quality_score = models.FloatField(default=0)
    rejection_reasons = models.JSONField(default=list, blank=True)
    approved_for_training = models.BooleanField(default=False)
    reviewed_by = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name="reviewed_training_candidates",
    )
    reviewed_at = models.DateTimeField(null=True, blank=True)
    exported_at = models.DateTimeField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "recommendation_training_candidates"
        ordering = ["-quality_score", "-created_at"]

    def __str__(self):
        return f"training_candidate:{self.source_session_id}:{self.status}"
