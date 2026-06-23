import shutil
import tempfile

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from rest_framework import status
from rest_framework.test import APITestCase
from django.core.files.uploadedfile import SimpleUploadedFile

from .models import Comment, Post, PostImage


User = get_user_model()


TEST_STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


class CommunityPostAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="writer@example.com",
            password="ValidPass123!",
            nickname="writer",
        )
        self.other_user = User.objects.create_user(
            email="other-writer@example.com",
            password="ValidPass123!",
            nickname="other",
        )
        self.post = Post.objects.create(
            author=self.user,
            category=Post.Category.PERFORMANCE_REVIEW,
            title="First Post",
            content="<p>Hello</p>",
            content_format=Post.ContentFormat.HTML,
        )

    def test_post_list_is_public(self):
        response = self.client.get(reverse("community_post_list"))

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(response.data["results"][0]["title"], "First Post")

    def test_post_create_requires_authentication(self):
        response = self.client.post(
            reverse("community_post_list"),
            {"title": "No Auth", "content": "body", "content_format": "markdown"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_user_can_create_post(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("community_post_list"),
            {
                "title": "Created Post",
                "content": "## Markdown body",
                "content_format": "markdown",
                "thumbnail_url": "https://example.com/thumb.jpg",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["author_email"], self.user.email)
        self.assertEqual(response.data["author_display_name"], "writer")
        self.assertEqual(response.data["category"], Post.Category.FREE_DISCUSSION)
        self.assertEqual(response.data["category_label"], "자유토론")
        self.assertTrue(Post.objects.filter(title="Created Post", author=self.user).exists())

    def test_authenticated_user_can_create_post_with_korean_category(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("community_post_list"),
            {
                "category": "공연추천",
                "title": "Recommended Post",
                "content": "body",
                "content_format": "markdown",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["category"], Post.Category.PERFORMANCE_RECOMMENDATION)
        self.assertEqual(response.data["category_label"], "공연추천")

    def test_post_list_filters_by_category(self):
        Post.objects.create(
            author=self.user,
            category=Post.Category.INFORMATION,
            title="Parking Tip",
            content="body",
            content_format=Post.ContentFormat.HTML,
        )

        response = self.client.get(
            reverse("community_post_list"),
            {"category": "정보공유"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(response.data["results"][0]["title"], "Parking Tip")
        self.assertEqual(response.data["results"][0]["category"], Post.Category.INFORMATION)

    def test_post_list_searches_title_and_content(self):
        Post.objects.create(
            author=self.user,
            category=Post.Category.INFORMATION,
            title="Parking Tip",
            content="예술의전당 주차 정보",
            content_format=Post.ContentFormat.HTML,
        )

        response = self.client.get(
            reverse("community_post_list"),
            {"search": "주차"},
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(response.data["results"][0]["title"], "Parking Tip")

    def test_post_author_display_name_falls_back_to_email(self):
        user = User.objects.create_user(
            email="no-nickname-post@example.com",
            password="ValidPass123!",
        )
        self.client.force_authenticate(user=user)

        response = self.client.post(
            reverse("community_post_list"),
            {
                "title": "No Nickname Post",
                "content": "body",
                "content_format": "markdown",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["author_nickname"], "")
        self.assertEqual(response.data["author_display_name"], "no-nickname-post@example.com")

    def test_only_author_can_update_or_delete_post(self):
        detail_url = reverse("community_post_detail", kwargs={"pk": self.post.pk})
        self.client.force_authenticate(user=self.other_user)

        forbidden_response = self.client.patch(
            detail_url,
            {"title": "Hacked"},
            format="json",
        )

        self.assertEqual(forbidden_response.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.user)
        update_response = self.client.patch(
            detail_url,
            {"title": "Updated"},
            format="json",
        )
        delete_response = self.client.delete(detail_url)

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["title"], "Updated")
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)


class CommunityCommentAPITests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="commenter@example.com",
            password="ValidPass123!",
            nickname="commenter",
        )
        self.other_user = User.objects.create_user(
            email="other-commenter@example.com",
            password="ValidPass123!",
            nickname="other",
        )
        self.post = Post.objects.create(
            author=self.user,
            title="Comment Post",
            content="body",
            content_format=Post.ContentFormat.HTML,
        )
        self.comment = Comment.objects.create(
            post=self.post,
            author=self.user,
            content="first comment",
        )

    def test_comment_list_is_public(self):
        response = self.client.get(
            reverse("community_comment_list", kwargs={"post_id": self.post.pk})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["total"], 1)
        self.assertEqual(response.data["results"][0]["content"], "first comment")

    def test_comment_create_requires_authentication(self):
        response = self.client.post(
            reverse("community_comment_list", kwargs={"post_id": self.post.pk}),
            {"content": "no auth"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_authenticated_user_can_create_comment(self):
        self.client.force_authenticate(user=self.other_user)

        response = self.client.post(
            reverse("community_comment_list", kwargs={"post_id": self.post.pk}),
            {"content": "new comment"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["author_email"], self.other_user.email)
        self.assertEqual(response.data["author_display_name"], "other")

    def test_comment_author_display_name_falls_back_to_email(self):
        user = User.objects.create_user(
            email="no-nickname-comment@example.com",
            password="ValidPass123!",
        )
        self.client.force_authenticate(user=user)

        response = self.client.post(
            reverse("community_comment_list", kwargs={"post_id": self.post.pk}),
            {"content": "new comment"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertEqual(response.data["author_nickname"], "")
        self.assertEqual(response.data["author_display_name"], "no-nickname-comment@example.com")

    def test_only_author_can_update_or_delete_comment(self):
        detail_url = reverse("community_comment_detail", kwargs={"pk": self.comment.pk})
        self.client.force_authenticate(user=self.other_user)

        forbidden_response = self.client.patch(
            detail_url,
            {"content": "hacked"},
            format="json",
        )

        self.assertEqual(forbidden_response.status_code, status.HTTP_403_FORBIDDEN)

        self.client.force_authenticate(user=self.user)
        update_response = self.client.patch(
            detail_url,
            {"content": "updated comment"},
            format="json",
        )
        delete_response = self.client.delete(detail_url)

        self.assertEqual(update_response.status_code, status.HTTP_200_OK)
        self.assertEqual(update_response.data["content"], "updated comment")
        self.assertEqual(delete_response.status_code, status.HTTP_204_NO_CONTENT)


@override_settings(STORAGES=TEST_STORAGES)
class CommunityImageUploadAPITests(APITestCase):
    def setUp(self):
        self.media_root = tempfile.mkdtemp()
        self.override = override_settings(MEDIA_ROOT=self.media_root)
        self.override.enable()
        self.user = User.objects.create_user(
            email="image@example.com",
            password="ValidPass123!",
            nickname="image",
        )

    def tearDown(self):
        self.override.disable()
        shutil.rmtree(self.media_root, ignore_errors=True)

    def _gif_file(self, name="test.gif", content_type="image/gif", payload=b""):
        data = (
            b"GIF89a\x01\x00\x01\x00\x80\x00\x00\x00\x00\x00\xff\xff\xff,"
            b"\x00\x00\x00\x00\x01\x00\x01\x00\x00\x02\x02D\x01\x00;"
            + payload
        )
        return SimpleUploadedFile(name, data, content_type=content_type)

    def test_image_upload_requires_authentication(self):
        response = self.client.post(
            reverse("community_image_upload"),
            {"image": self._gif_file()},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_401_UNAUTHORIZED)

    def test_image_upload_success(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("community_image_upload"),
            {"image": self._gif_file()},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("/media/community/images/", response.data["image_url"])
        self.assertEqual(PostImage.objects.count(), 1)
        self.assertEqual(PostImage.objects.first().uploader, self.user)

    def test_image_upload_rejects_invalid_content_type(self):
        self.client.force_authenticate(user=self.user)
        file = SimpleUploadedFile("text.txt", b"hello", content_type="text/plain")

        response = self.client.post(
            reverse("community_image_upload"),
            {"image": file},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_image_upload_rejects_file_over_5mb(self):
        self.client.force_authenticate(user=self.user)
        large_file = self._gif_file(payload=b"0" * (5 * 1024 * 1024 + 1))

        response = self.client.post(
            reverse("community_image_upload"),
            {"image": large_file},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
