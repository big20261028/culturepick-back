from django.urls import path

from .views import AIRecommendationView, RecommendationFeedbackView

urlpatterns = [
    path("ai/", AIRecommendationView.as_view(), name="recommendation_ai"),
    path("<int:session_id>/feedback/", RecommendationFeedbackView.as_view(), name="recommendation_feedback"),
]
