from django.urls import path

from .views import PerformanceActionView, PerformanceDetailView, PerformanceListView

urlpatterns = [
    path("", PerformanceListView.as_view(), name="performance_list"),
    path("<str:performance_id>/actions/", PerformanceActionView.as_view(), name="performance_action"),
    path("<str:performance_id>/", PerformanceDetailView.as_view(), name="performance_detail"),
]
