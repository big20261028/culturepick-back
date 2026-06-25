import logging

from django.db.models import Count, F, Q
from django.shortcuts import get_object_or_404
from rest_framework import generics, status
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, MultiPartParser
from rest_framework.permissions import SAFE_METHODS, AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Comment, Post, normalize_post_category
from .permissions import IsAuthorOrReadOnly
from .serializers import CommentSerializer, PostImageUploadSerializer, PostSerializer


logger = logging.getLogger(__name__)


class PostListCreateView(generics.ListCreateAPIView):
    serializer_class = PostSerializer

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        queryset = (
            Post.objects.select_related("author")
            .annotate(comment_count=Count("comments"))
            .order_by("-created_at", "-id")
        )

        category_param = (
            self.request.query_params.get("category")
            or self.request.query_params.get("category_slug")
            or ""
        )
        category = normalize_post_category(category_param)
        if category is None:
            raise ValidationError({"category": "Invalid category."})
        if category:
            queryset = queryset.filter(category=category)

        keyword = (
            self.request.query_params.get("keyword")
            or self.request.query_params.get("search")
            or self.request.query_params.get("q")
            or ""
        ).strip()
        if keyword:
            queryset = queryset.filter(Q(title__icontains=keyword) | Q(content__icontains=keyword))
        return queryset

    def perform_create(self, serializer):
        serializer.save(author=self.request.user)


class PostDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = PostSerializer

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [AllowAny()]
        return [IsAuthenticated(), IsAuthorOrReadOnly()]

    def get_queryset(self):
        return Post.objects.select_related("author").annotate(comment_count=Count("comments"))

    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        Post.objects.filter(pk=instance.pk).update(view_count=F("view_count") + 1)
        instance.view_count += 1
        serializer = self.get_serializer(instance)
        return Response(serializer.data)


class CommentListCreateView(generics.ListCreateAPIView):
    serializer_class = CommentSerializer

    def get_permissions(self):
        if self.request.method == "GET":
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_queryset(self):
        return (
            Comment.objects.filter(post_id=self.kwargs["post_id"])
            .select_related("author", "post")
            .order_by("created_at", "id")
        )

    def perform_create(self, serializer):
        post = get_object_or_404(Post, pk=self.kwargs["post_id"])
        serializer.save(post=post, author=self.request.user)


class CommentDetailView(generics.RetrieveUpdateDestroyAPIView):
    serializer_class = CommentSerializer
    queryset = Comment.objects.select_related("author", "post")

    def get_permissions(self):
        if self.request.method in SAFE_METHODS:
            return [AllowAny()]
        return [IsAuthenticated(), IsAuthorOrReadOnly()]

    def destroy(self, request, *args, **kwargs):
        instance = self.get_object()
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)


class PostImageUploadView(APIView):
    permission_classes = [IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser]

    def post(self, request):
        data = request.data
        if "image" not in request.FILES and "image" not in request.data:
            uploaded_file = request.FILES.get("file") or request.data.get("file")
            if uploaded_file is not None:
                data = {key: request.data.get(key) for key in request.data.keys()}
                data["image"] = uploaded_file

        logger.info("community image upload requested: file_keys=%s", list(request.FILES.keys()))
        serializer = PostImageUploadSerializer(data=data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        image = serializer.save()
        logger.info("community image uploaded: id=%s name=%s url=%s", image.pk, image.image.name, image.image.url)
        return Response(
            PostImageUploadSerializer(image, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )
