from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.logs.services import request_user_or_none
from apps.performances.models import Performance

from .models import RecommendationSession
from .serializers import (
    AIRecommendationRequestSerializer,
    RecommendationFeedbackSerializer,
    RecommendationItemSerializer,
)
from .services import create_ai_recommendation
from .services import record_feedback_and_update_quality


class AIRecommendationView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = AIRecommendationRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        session = create_ai_recommendation(
            user=request_user_or_none(request),
            message=serializer.validated_data["message"],
            limit=serializer.validated_data["limit"],
            candidate_limit=serializer.validated_data["candidate_limit"],
        )
        items = session.items.select_related("performance__venue").all()
        result_serializer = RecommendationItemSerializer(
            items,
            many=True,
            context={"request": request},
        )

        return Response({
            "session_id": session.id,
            "summary": session.parsed_response.get("summary", ""),
            "fallback_used": session.fallback_used,
            "validation_status": session.validation_status,
            "results": result_serializer.data,
        }, status=status.HTTP_200_OK)


class RecommendationFeedbackView(APIView):
    permission_classes = [AllowAny]

    def post(self, request, session_id):
        session = get_object_or_404(RecommendationSession, pk=session_id)
        serializer = RecommendationFeedbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        performance_id = serializer.validated_data.pop("performance_id", "")
        performance = Performance.objects.filter(pk=performance_id).first() if performance_id else None
        feedback = record_feedback_and_update_quality(
            session=session,
            user=request_user_or_none(request),
            performance=performance,
            feedback_type=serializer.validated_data["feedback_type"],
            metadata=serializer.validated_data.get("metadata", {}),
        )
        return Response(
            RecommendationFeedbackSerializer(feedback).data,
            status=status.HTTP_201_CREATED,
        )
