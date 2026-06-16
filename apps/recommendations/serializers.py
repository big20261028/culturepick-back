from rest_framework import serializers

from apps.performances.models import Performance
from apps.performances.serializers import PerformanceListSerializer

from .models import RecommendationFeedback, RecommendationItem


class AIRecommendationRequestSerializer(serializers.Serializer):
    message = serializers.CharField(required=False, allow_blank=True, default="")
    limit = serializers.IntegerField(required=False, min_value=1, max_value=10, default=5)
    candidate_limit = serializers.IntegerField(required=False, min_value=10, max_value=50, default=30)


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
