from __future__ import annotations

import uuid
from pathlib import Path

from django.conf import settings
from django.db import models
from django.utils import timezone


def community_image_upload_to(instance, filename: str) -> str:
    ext = Path(filename).suffix.lower()
    today = timezone.now()
    return f"community/images/{today:%Y/%m/%d}/{uuid.uuid4().hex}{ext}"


class Post(models.Model):
    class ContentFormat(models.TextChoices):
        HTML = "html", "html"
        MARKDOWN = "markdown", "markdown"
        JSON = "json", "json"

    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="community_posts",
    )
    title = models.CharField(max_length=200)
    content = models.TextField()
    content_format = models.CharField(
        max_length=20,
        choices=ContentFormat.choices,
        default=ContentFormat.HTML,
    )
    thumbnail_url = models.URLField(max_length=1000, blank=True)
    view_count = models.PositiveIntegerField(default=0)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "community_posts"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"{self.title} ({self.pk})"


class Comment(models.Model):
    post = models.ForeignKey(Post, on_delete=models.CASCADE, related_name="comments")
    author = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="community_comments",
    )
    content = models.TextField()
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = "community_comments"
        ordering = ["created_at", "id"]

    def __str__(self):
        return f"comment:{self.pk}:post:{self.post_id}"


class PostImage(models.Model):
    uploader = models.ForeignKey(
        settings.AUTH_USER_MODEL,
        on_delete=models.CASCADE,
        related_name="community_images",
    )
    image = models.ImageField(upload_to=community_image_upload_to)
    original_name = models.CharField(max_length=255)
    size = models.PositiveIntegerField()
    content_type = models.CharField(max_length=100)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "community_post_images"
        ordering = ["-created_at", "-id"]

    def __str__(self):
        return f"image:{self.pk}:{self.original_name}"
