from django.conf import settings
from rest_framework import serializers

from apps.performances.models import Performance
from apps.performances.serializers import PerformanceListSerializer

from .models import RecommendationFeedback, RecommendationItem


class AIRecommendationRequestSerializer(serializers.Serializer):
    message = serializers.CharField(required=False, allow_blank=True, default="")
    prompt = serializers.CharField(required=False, allow_blank=True, write_only=True)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=10, default=5)
    candidate_limit = serializers.IntegerField(
        required=False,
        min_value=3,
        max_value=20,
        default=getattr(settings, "AI_RECOMMENDATION_CANDIDATE_LIMIT_DEFAULT", 12),
    )
    session_id = serializers.IntegerField(required=False, allow_null=True)
    include_candidates = serializers.BooleanField(required=False, default=False)

    def validate(self, attrs):
        message = (attrs.get("message") or "").strip()
        prompt = (attrs.get("prompt") or "").strip()
        attrs["message"] = message or prompt
        return attrs


class RecommendationCandidateRequestSerializer(serializers.Serializer):
    message = serializers.CharField(required=False, allow_blank=True, default="")
    prompt = serializers.CharField(required=False, allow_blank=True, write_only=True)
    limit = serializers.IntegerField(required=False, min_value=1, max_value=50, default=30)

    def validate(self, attrs):
        message = (attrs.get("message") or "").strip()
        prompt = (attrs.get("prompt") or "").strip()
        attrs["message"] = message or prompt
        return attrs


class RecommendationItemSerializer(serializers.ModelSerializer):
    performance = PerformanceListSerializer(read_only=True)

    class Meta:
        model = RecommendationItem
        fields = (
            "id",
            "rank",
            "score",
            "reason",
            "source",
            "performance",
        )


class RecommendationCandidateSerializer(serializers.Serializer):
    performance = PerformanceListSerializer(read_only=True)
    score = serializers.FloatField()
    reasons = serializers.ListField(child=serializers.CharField())
    contributions = serializers.ListField(child=serializers.DictField(), required=False)


def serialize_candidate(candidate):
    return {
        "performance": candidate.performance,
        "score": candidate.score,
        "reasons": candidate.reasons,
        "contributions": candidate.contributions,
    }


class RecommendationFeedbackSerializer(serializers.ModelSerializer):
    performance_id = serializers.CharField(required=False, allow_blank=True, write_only=True)

    class Meta:
        model = RecommendationFeedback
        fields = (
            "id",
            "performance_id",
            "feedback_type",
            "metadata",
            "created_at",
        )
        read_only_fields = ("id", "created_at")

    def validate_performance_id(self, value):
        if value and not Performance.objects.filter(pk=value).exists():
            raise serializers.ValidationError("Unknown performance_id.")
        return value
