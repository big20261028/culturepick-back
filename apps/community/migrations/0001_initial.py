import apps.community.models
import django.db.models.deletion
from django.conf import settings
from django.db import migrations, models


class Migration(migrations.Migration):

    initial = True

    dependencies = [
        migrations.swappable_dependency(settings.AUTH_USER_MODEL),
    ]

    operations = [
        migrations.CreateModel(
            name="Post",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("title", models.CharField(max_length=200)),
                ("content", models.TextField()),
                (
                    "content_format",
                    models.CharField(
                        choices=[("html", "html"), ("markdown", "markdown"), ("json", "json")],
                        default="html",
                        max_length=20,
                    ),
                ),
                ("thumbnail_url", models.URLField(blank=True, max_length=1000)),
                ("view_count", models.PositiveIntegerField(default=0)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "author",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="community_posts",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "community_posts",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.CreateModel(
            name="PostImage",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("image", models.ImageField(upload_to=apps.community.models.community_image_upload_to)),
                ("original_name", models.CharField(max_length=255)),
                ("size", models.PositiveIntegerField()),
                ("content_type", models.CharField(max_length=100)),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                (
                    "uploader",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="community_images",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
            ],
            options={
                "db_table": "community_post_images",
                "ordering": ["-created_at", "-id"],
            },
        ),
        migrations.CreateModel(
            name="Comment",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("content", models.TextField()),
                ("created_at", models.DateTimeField(auto_now_add=True)),
                ("updated_at", models.DateTimeField(auto_now=True)),
                (
                    "author",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="community_comments",
                        to=settings.AUTH_USER_MODEL,
                    ),
                ),
                (
                    "post",
                    models.ForeignKey(
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="comments",
                        to="community.post",
                    ),
                ),
            ],
            options={
                "db_table": "community_comments",
                "ordering": ["created_at", "id"],
            },
        ),
    ]
