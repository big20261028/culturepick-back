from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from apps.logs.services import request_user_or_none
from apps.performances.models import Performance

from .models import RecommendationSession
from .serializers import (
    AIRecommendationRequestSerializer,
    RecommendationCandidateRequestSerializer,
    RecommendationCandidateSerializer,
    RecommendationFeedbackSerializer,
    RecommendationItemSerializer,
    serialize_candidate,
)
from .services import create_ai_recommendation, get_recommendation_candidates
from .services import record_feedback_and_update_quality


class RecommendationCandidateView(APIView):
    permission_classes = [AllowAny]

    def post(self, request):
        serializer = RecommendationCandidateRequestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        profile_snapshot, candidates = get_recommendation_candidates(
            user=request_user_or_none(request),
            message=serializer.validated_data["message"],
            limit=serializer.validated_data["limit"],
        )
        candidate_serializer = RecommendationCandidateSerializer(
            [serialize_candidate(candidate) for candidate in candidates],
            many=True,
            context={"request": request},
        )
        return Response({
            "message": serializer.validated_data["message"],
            "profile": profile_snapshot,
            "total": len(candidate_serializer.data),
            "candidates": candidate_serializer.data,
        })


class AIRecommendationView(APIView):
    permission_classes = [IsAuthenticated]

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

        recommendations = [
            {
                "performance_id": item["performance"]["performance_id"],
                "title": item["performance"]["title"],
                "reason": item["reason"],
                "rank": item["rank"],
                "source": item["source"],
                "score": item["score"],
            }
            for item in result_serializer.data
        ]
        response_data = {
            "session_id": session.id,
            "summary": session.parsed_response.get("summary", ""),
            "message": session.parsed_response.get("summary", ""),
            "fallback_used": session.fallback_used,
            "validation_status": session.validation_status,
            "recommendations": recommendations,
            "results": result_serializer.data,
        }
        if serializer.validated_data["include_candidates"]:
            response_data["profile"] = session.user_profile_snapshot
            response_data["candidates"] = session.candidate_snapshot
        return Response(response_data, status=status.HTTP_200_OK)


class RecommendationFeedbackView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, session_id):
        session = get_object_or_404(RecommendationSession, pk=session_id, user=request.user)
        serializer = RecommendationFeedbackSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        performance_id = serializer.validated_data.pop("performance_id", "")
        performance = Performance.objects.filter(pk=performance_id).first() if performance_id else None
        if performance and not session.items.filter(performance=performance).exists():
            return Response(
                {"performance_id": "This performance was not recommended in the session."},
                status=status.HTTP_400_BAD_REQUEST,
            )
        feedback = record_feedback_and_update_quality(
            session=session,
            user=request.user,
            performance=performance,
            feedback_type=serializer.validated_data["feedback_type"],
            metadata=serializer.validated_data.get("metadata", {}),
        )
        return Response(
            RecommendationFeedbackSerializer(feedback).data,
            status=status.HTTP_201_CREATED,
        )
