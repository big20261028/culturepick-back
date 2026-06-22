from django.urls import path

from .views import (
    CommentDetailView,
    CommentListCreateView,
    PostDetailView,
    PostImageUploadView,
    PostListCreateView,
)

urlpatterns = [
    path("posts/", PostListCreateView.as_view(), name="community_post_list"),
    path("posts/<int:pk>/", PostDetailView.as_view(), name="community_post_detail"),
    path("posts/<int:post_id>/comments/", CommentListCreateView.as_view(), name="community_comment_list"),
    path("comments/<int:pk>/", CommentDetailView.as_view(), name="community_comment_detail"),
    path("images/", PostImageUploadView.as_view(), name="community_image_upload"),
]
