import shutil
import tempfile
from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
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

    def test_html_post_create_sanitizes_tags_attributes_and_urls(self):
        self.client.force_authenticate(user=self.user)
        unsafe_html = """
            <h2 id="heading">Review</h2>
            <p class="lead" style="color:red" onclick="alert(1)">
              Safe <strong style="font-size:99px">bold</strong>
              <a href="javascript:alert(1)" id="bad-link">bad link</a>
              <a href="https://example.com/review">safe link</a>
            </p>
            <script>alert('script')</script>
            <iframe>iframe payload</iframe>
            <svg><text>svg payload</text></svg>
            <form>form payload</form>
            <object>object payload</object>
            <embed src="https://example.com/plugin">
            <style>.owned { display: block; }</style>
            <img src="data:image/svg+xml;base64,PHN2Zz4=" alt="bad">
            <img src="mailto:image@example.com" alt="bad mail image">
            <img src="/media/community/images/poster.jpg" alt="poster"
                 title="show" onerror="alert(1)" class="poster">
        """

        response = self.client.post(
            reverse("community_post_list"),
            {
                "title": "Sanitized post",
                "content": unsafe_html,
                "content_format": "html",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        post = Post.objects.get(pk=response.data["id"])
        self.assertEqual(response.data["content"], post.content)
        self.assertIn("<h2>Review</h2>", post.content)
        self.assertIn("<strong>bold</strong>", post.content)
        self.assertIn('href="https://example.com/review"', post.content)
        self.assertIn('src="/media/community/images/poster.jpg"', post.content)
        self.assertIn('alt="poster"', post.content)
        self.assertIn('title="show"', post.content)
        for forbidden in (
            "onclick",
            "style=",
            "class=",
            "id=",
            "javascript:",
            "data:image",
            "mailto:image",
            ".owned",
            "script payload",
            "alert('script')",
            "iframe payload",
            "svg payload",
            "form payload",
            "object payload",
            "<embed",
        ):
            self.assertNotIn(forbidden, post.content)

    def test_html_post_keeps_the_tiptap_allowlist(self):
        self.client.force_authenticate(user=self.user)
        allowed_html = (
            "<h2>Heading 2</h2><h3>Heading 3</h3>"
            "<p>paragraph<br><strong>strong</strong><em>emphasis</em>"
            "<s>strike</s><u>underline</u></p>"
            "<ul><li>unordered</li></ul><ol><li>ordered</li></ol>"
            "<blockquote>quote</blockquote><hr>"
            "<pre><code>print('safe')</code></pre>"
            '<a href="mailto:user@example.com">email</a>'
            '<img src="/media/community/images/poster.png" alt="poster" title="title">'
        )

        response = self.client.post(
            reverse("community_post_list"),
            {
                "title": "Allowlist post",
                "content": allowed_html,
                "content_format": "html",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        sanitized = response.data["content"]
        for tag in (
            "h2",
            "h3",
            "p",
            "br",
            "strong",
            "em",
            "s",
            "u",
            "ul",
            "ol",
            "li",
            "blockquote",
            "hr",
            "pre",
            "code",
            "a",
            "img",
        ):
            self.assertIn(f"<{tag}", sanitized)
        self.assertIn('href="mailto:user@example.com"', sanitized)

    @override_settings(COMMUNITY_ALLOWED_IMAGE_HOSTS={"cdn.example.com"})
    def test_html_post_allows_only_configured_https_image_hosts(self):
        self.client.force_authenticate(user=self.user)
        html = (
            "<p>Image sources</p>"
            '<img src="https://cdn.example.com/safe.jpg" alt="allowed">'
            '<img src="http://cdn.example.com/plain-http.jpg" alt="http">'
            '<img src="//cdn.example.com/protocol-relative.jpg" alt="relative-host">'
            '<img src="https://evil.example/track.jpg" alt="external">'
            '<img src="/media/../private/track.jpg" alt="traversal">'
        )

        response = self.client.post(
            reverse("community_post_list"),
            {
                "title": "Image host allowlist",
                "content": html,
                "content_format": "html",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        sanitized = response.data["content"]
        self.assertIn('src="https://cdn.example.com/safe.jpg"', sanitized)
        for forbidden in (
            "plain-http.jpg",
            "protocol-relative.jpg",
            "evil.example",
            "/media/../private",
        ):
            self.assertNotIn(forbidden, sanitized)

    def test_html_post_patch_sanitizes_before_saving(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            reverse("community_post_detail", kwargs={"pk": self.post.pk}),
            {
                "content": (
                    '<h3 onmouseover="alert(1)">Updated</h3>'
                    '<img src="/media/community/images/safe.png" onerror="alert(2)">'
                )
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.post.refresh_from_db()
        self.assertIn("<h3>Updated</h3>", self.post.content)
        self.assertIn('src="/media/community/images/safe.png"', self.post.content)
        self.assertNotIn("onmouseover", self.post.content)
        self.assertNotIn("onerror", self.post.content)

    def test_changing_content_format_to_html_sanitizes_existing_body(self):
        self.post.content_format = Post.ContentFormat.MARKDOWN
        self.post.content = "<script>alert(1)</script><p>Visible</p>"
        self.post.save(update_fields=["content_format", "content"])
        self.client.force_authenticate(user=self.user)

        response = self.client.patch(
            reverse("community_post_detail", kwargs={"pk": self.post.pk}),
            {"content_format": "html"},
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.post.refresh_from_db()
        self.assertEqual(self.post.content, "<p>Visible</p>")

    def test_markdown_content_is_not_html_sanitized(self):
        self.client.force_authenticate(user=self.user)
        markdown = "<script>shown as code-like text</script>\n[link](javascript:example)"

        response = self.client.post(
            reverse("community_post_list"),
            {
                "title": "Markdown post",
                "content": markdown,
                "content_format": "markdown",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        post = Post.objects.get(pk=response.data["id"])
        self.assertEqual(post.content, markdown)
        self.assertEqual(response.data["content"], markdown)

    def test_html_post_rejects_body_without_meaningful_content(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("community_post_list"),
            {
                "title": "Empty after sanitize",
                "content": (
                    "<p>&nbsp;<br></p><script>alert(1)</script>"
                    '<img src="data:image/png;base64,AAAA" alt="removed">'
                ),
                "content_format": "html",
            },
            format="json",
        )

        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertIn("content", response.data["detail"])

    def test_legacy_html_is_sanitized_in_response_without_rewriting_database(self):
        unsafe_content = '<p onclick="alert(1)">Legacy</p><script>alert(2)</script>'
        self.post.content = unsafe_content
        self.post.save(update_fields=["content"])

        response = self.client.get(
            reverse("community_post_detail", kwargs={"pk": self.post.pk})
        )

        self.assertEqual(response.status_code, status.HTTP_200_OK)
        self.assertEqual(response.data["content"], "<p>Legacy</p>")
        self.post.refresh_from_db()
        self.assertEqual(self.post.content, unsafe_content)


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


class CommunityHTMLSanitizeCommandTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            email="sanitize-command@example.com",
            password="ValidPass123!",
        )

    def test_command_is_dry_run_by_default(self):
        unsafe_content = '<p onclick="alert(1)">Safe</p>'
        post = Post.objects.create(
            author=self.user,
            title="Dry run",
            content=unsafe_content,
            content_format=Post.ContentFormat.HTML,
        )
        stdout = StringIO()

        call_command("sanitize_community_html", stdout=stdout)

        post.refresh_from_db()
        self.assertEqual(post.content, unsafe_content)
        self.assertIn("mode=dry-run", stdout.getvalue())
        self.assertIn("changed=1", stdout.getvalue())
        self.assertIn("applied=0", stdout.getvalue())

    def test_command_apply_sanitizes_safe_result_and_skips_empty_result(self):
        sanitizable = Post.objects.create(
            author=self.user,
            title="Apply",
            content='<p onclick="alert(1)">Safe</p><script>alert(2)</script>',
            content_format=Post.ContentFormat.HTML,
        )
        manual_review = Post.objects.create(
            author=self.user,
            title="Manual review",
            content="<script>alert(3)</script>",
            content_format=Post.ContentFormat.HTML,
        )
        stdout = StringIO()

        call_command("sanitize_community_html", apply=True, stdout=stdout)

        sanitizable.refresh_from_db()
        manual_review.refresh_from_db()
        self.assertEqual(sanitizable.content, "<p>Safe</p>")
        self.assertEqual(manual_review.content, "<script>alert(3)</script>")
        self.assertIn("mode=apply", stdout.getvalue())
        self.assertIn("changed=2", stdout.getvalue())
        self.assertIn("applied=1", stdout.getvalue())
        self.assertIn("manual_review=1", stdout.getvalue())
        self.assertIn(str(manual_review.pk), stdout.getvalue())


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
        self.assertEqual(response.data["url"], response.data["image_url"])
        self.assertEqual(PostImage.objects.count(), 1)
        self.assertEqual(PostImage.objects.first().uploader, self.user)

    def test_image_upload_accepts_file_field_alias(self):
        self.client.force_authenticate(user=self.user)

        response = self.client.post(
            reverse("community_image_upload"),
            {"file": self._gif_file()},
            format="multipart",
        )

        self.assertEqual(response.status_code, status.HTTP_201_CREATED)
        self.assertIn("/media/community/images/", response.data["url"])
        self.assertEqual(PostImage.objects.count(), 1)

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
