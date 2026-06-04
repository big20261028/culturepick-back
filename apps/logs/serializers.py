from rest_framework import serializers

from .models import QnALog, SearchLog, ViewLog


class SearchLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = SearchLog
        fields = (
            "id",
            "keyword",
            "filter_region",
            "filter_genre",
            "filter_status",
            "created_at",
        )
        read_only_fields = ("id", "created_at")


class ViewLogSerializer(serializers.ModelSerializer):
    class Meta:
        model = ViewLog
        fields = (
            "id",
            "performance_id",
            "log_type",
            "created_at",
        )
        read_only_fields = ("id", "created_at")


class QnALogSerializer(serializers.ModelSerializer):
    class Meta:
        model = QnALog
        fields = (
            "id",
            "question",
            "answer",
            "created_at",
        )
        read_only_fields = ("id", "created_at")
