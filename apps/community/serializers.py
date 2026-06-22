from rest_framework import serializers

from apps.users.serializers import user_display_name

from .models import Comment, Post, PostImage


ALLOWED_IMAGE_CONTENT_TYPES = {
    "image/jpeg",
    "image/png",
    "image/webp",
    "image/gif",
}
MAX_IMAGE_SIZE = 5 * 1024 * 1024


class PostSerializer(serializers.ModelSerializer):
    author_email = serializers.EmailField(source="author.email", read_only=True)
    author_nickname = serializers.CharField(source="author.nickname", read_only=True)
    author_display_name = serializers.SerializerMethodField()
    comment_count = serializers.IntegerField(read_only=True)

    class Meta:
        model = Post
        fields = (
            "id",
            "author",
            "author_email",
            "author_nickname",
            "author_display_name",
            "title",
            "content",
            "content_format",
            "thumbnail_url",
            "view_count",
            "comment_count",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "author",
            "author_email",
            "author_nickname",
            "author_display_name",
            "view_count",
            "comment_count",
            "created_at",
            "updated_at",
        )

    def get_author_display_name(self, obj):
        return user_display_name(obj.author)

    def validate_title(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Title is required.")
        return value

    def validate_content(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Content is required.")
        return value


class CommentSerializer(serializers.ModelSerializer):
    author_email = serializers.EmailField(source="author.email", read_only=True)
    author_nickname = serializers.CharField(source="author.nickname", read_only=True)
    author_display_name = serializers.SerializerMethodField()

    class Meta:
        model = Comment
        fields = (
            "id",
            "post",
            "author",
            "author_email",
            "author_nickname",
            "author_display_name",
            "content",
            "created_at",
            "updated_at",
        )
        read_only_fields = (
            "id",
            "post",
            "author",
            "author_email",
            "author_nickname",
            "author_display_name",
            "created_at",
            "updated_at",
        )

    def get_author_display_name(self, obj):
        return user_display_name(obj.author)

    def validate_content(self, value):
        value = value.strip()
        if not value:
            raise serializers.ValidationError("Content is required.")
        return value


class PostImageUploadSerializer(serializers.ModelSerializer):
    image_url = serializers.SerializerMethodField(read_only=True)

    class Meta:
        model = PostImage
        fields = (
            "id",
            "image",
            "image_url",
            "original_name",
            "size",
            "content_type",
            "created_at",
        )
        read_only_fields = (
            "id",
            "image_url",
            "original_name",
            "size",
            "content_type",
            "created_at",
        )

    def validate_image(self, image):
        content_type = getattr(image, "content_type", "")
        if content_type not in ALLOWED_IMAGE_CONTENT_TYPES:
            raise serializers.ValidationError("Unsupported image type.")
        if image.size > MAX_IMAGE_SIZE:
            raise serializers.ValidationError("Image size must be 5MB or less.")
        return image

    def create(self, validated_data):
        image = validated_data["image"]
        return PostImage.objects.create(
            uploader=self.context["request"].user,
            image=image,
            original_name=image.name,
            size=image.size,
            content_type=getattr(image, "content_type", ""),
        )

    def get_image_url(self, obj):
        request = self.context.get("request")
        url = obj.image.url if obj.image else ""
        if request and url.startswith("/"):
            return request.build_absolute_uri(url)
        return url
