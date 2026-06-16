from django.contrib import admin
from django.utils import timezone

from .models import (
    PerformanceVector,
    RecommendationFeedback,
    RecommendationItem,
    RecommendationSession,
    TrainingExampleCandidate,
    UserPreferenceProfile,
)


class RecommendationItemInline(admin.TabularInline):
    model = RecommendationItem
    extra = 0
    readonly_fields = ("performance", "rank", "score", "reason", "source", "created_at")
    can_delete = False


class RecommendationFeedbackInline(admin.TabularInline):
    model = RecommendationFeedback
    extra = 0
    readonly_fields = ("user", "performance", "feedback_type", "metadata", "created_at")
    can_delete = False


@admin.register(RecommendationSession)
class RecommendationSessionAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "user",
        "provider",
        "model_name",
        "validation_status",
        "fallback_used",
        "quality_score",
        "created_at",
    )
    list_filter = ("provider", "validation_status", "fallback_used", "created_at")
    search_fields = ("request_text", "model_name", "user__email")
    readonly_fields = (
        "user_profile_snapshot",
        "candidate_snapshot",
        "raw_response",
        "parsed_response",
        "created_at",
    )
    inlines = [RecommendationItemInline, RecommendationFeedbackInline]


@admin.register(TrainingExampleCandidate)
class TrainingExampleCandidateAdmin(admin.ModelAdmin):
    list_display = (
        "id",
        "source_session",
        "status",
        "training_task",
        "quality_score",
        "approved_for_training",
        "exported_at",
        "created_at",
    )
    list_filter = ("status", "training_task", "approved_for_training", "exported_at", "created_at")
    search_fields = ("source_session__request_text",)
    readonly_fields = (
        "source_session",
        "input_payload",
        "output_payload",
        "chosen_output",
        "rejected_output",
        "quality_score",
        "rejection_reasons",
        "created_at",
        "updated_at",
        "exported_at",
    )
    actions = ("approve_for_training", "reject_for_training")

    @admin.action(description="Approve selected candidates for training")
    def approve_for_training(self, request, queryset):
        queryset.update(
            status=TrainingExampleCandidate.Status.AUTO_APPROVED,
            approved_for_training=True,
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )

    @admin.action(description="Reject selected candidates")
    def reject_for_training(self, request, queryset):
        queryset.update(
            status=TrainingExampleCandidate.Status.REJECTED,
            approved_for_training=False,
            reviewed_by=request.user,
            reviewed_at=timezone.now(),
        )


@admin.register(UserPreferenceProfile)
class UserPreferenceProfileAdmin(admin.ModelAdmin):
    list_display = ("user", "is_stale", "version", "last_built_at", "updated_at")
    list_filter = ("is_stale", "version")
    search_fields = ("user__email",)
    readonly_fields = ("vector_data", "source_summary", "last_built_at", "updated_at")


@admin.register(PerformanceVector)
class PerformanceVectorAdmin(admin.ModelAdmin):
    list_display = ("performance", "version", "updated_at")
    search_fields = ("performance__performance_id", "performance__title")
    readonly_fields = ("vector_data", "source_summary", "updated_at")


@admin.register(RecommendationFeedback)
class RecommendationFeedbackAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "user", "performance", "feedback_type", "created_at")
    list_filter = ("feedback_type", "created_at")
    search_fields = ("session__request_text", "user__email", "performance__title")


@admin.register(RecommendationItem)
class RecommendationItemAdmin(admin.ModelAdmin):
    list_display = ("id", "session", "performance", "rank", "score", "source", "created_at")
    list_filter = ("source", "created_at")
    search_fields = ("performance__title", "performance__performance_id", "session__request_text")
