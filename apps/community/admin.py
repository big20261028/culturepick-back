from django.contrib import admin

from .models import Comment, Post, PostImage


class CommentInline(admin.TabularInline):
    model = Comment
    extra = 0
    readonly_fields = ("author", "content", "created_at", "updated_at")
    can_delete = False


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("id", "title", "category", "author", "content_format", "view_count", "created_at", "updated_at")
    list_filter = ("category", "content_format", "created_at")
    search_fields = ("title", "content", "author__email", "author__nickname")
    readonly_fields = ("view_count", "created_at", "updated_at")
    inlines = [CommentInline]


@admin.register(Comment)
class CommentAdmin(admin.ModelAdmin):
    list_display = ("id", "post", "author", "created_at", "updated_at")
    search_fields = ("content", "post__title", "author__email", "author__nickname")
    readonly_fields = ("created_at", "updated_at")


@admin.register(PostImage)
class PostImageAdmin(admin.ModelAdmin):
    list_display = ("id", "uploader", "original_name", "size", "content_type", "created_at")
    list_filter = ("content_type", "created_at")
    search_fields = ("original_name", "uploader__email", "uploader__nickname")
    readonly_fields = ("created_at",)
