from django.db import migrations, models


class Migration(migrations.Migration):

    dependencies = [
        ("logs", "0002_initial"),
    ]

    operations = [
        migrations.CreateModel(
            name="QnALogDailyAggregate",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("log_date", models.DateField(unique=True)),
                ("count", models.PositiveBigIntegerField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "qna_log_daily_aggregates",
            },
        ),
        migrations.CreateModel(
            name="SearchLogDailyAggregate",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("log_date", models.DateField()),
                ("filter_region", models.CharField(blank=True, max_length=100)),
                ("filter_genre", models.CharField(blank=True, max_length=100)),
                ("filter_status", models.CharField(blank=True, max_length=50)),
                ("count", models.PositiveBigIntegerField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "search_log_daily_aggregates",
            },
        ),
        migrations.CreateModel(
            name="ViewLogDailyAggregate",
            fields=[
                (
                    "id",
                    models.BigAutoField(
                        auto_created=True,
                        primary_key=True,
                        serialize=False,
                        verbose_name="ID",
                    ),
                ),
                ("log_date", models.DateField()),
                ("performance_id", models.CharField(max_length=20)),
                ("log_type", models.CharField(blank=True, max_length=50)),
                ("count", models.PositiveBigIntegerField(default=0)),
                ("updated_at", models.DateTimeField(auto_now=True)),
            ],
            options={
                "db_table": "view_log_daily_aggregates",
            },
        ),
        migrations.AddIndex(
            model_name="qnalog",
            index=models.Index(
                fields=["created_at"],
                name="qna_logs_created_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="searchlog",
            index=models.Index(
                fields=["created_at"],
                name="search_logs_created_idx",
            ),
        ),
        migrations.AddIndex(
            model_name="viewlog",
            index=models.Index(
                fields=["created_at"],
                name="view_logs_created_idx",
            ),
        ),
        migrations.AddConstraint(
            model_name="searchlogdailyaggregate",
            constraint=models.UniqueConstraint(
                fields=(
                    "log_date",
                    "filter_region",
                    "filter_genre",
                    "filter_status",
                ),
                name="unique_search_log_daily_bucket",
            ),
        ),
        migrations.AddConstraint(
            model_name="viewlogdailyaggregate",
            constraint=models.UniqueConstraint(
                fields=("log_date", "performance_id", "log_type"),
                name="unique_view_log_daily_bucket",
            ),
        ),
    ]
