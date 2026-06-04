from django.urls import path

from .views import QnALogCreateView, SearchLogCreateView, ViewLogCreateView

urlpatterns = [
    path("search/", SearchLogCreateView.as_view(), name="log_search"),
    path("view/", ViewLogCreateView.as_view(), name="log_view"),
    path("qna/", QnALogCreateView.as_view(), name="log_qna"),
]
