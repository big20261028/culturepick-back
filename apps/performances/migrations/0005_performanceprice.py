from django.db import migrations, models
import django.db.models.deletion


class Migration(migrations.Migration):

    dependencies = [
        ("performances", "0004_performance_agency_performance_facility_name_and_more"),
    ]

    operations = [
        migrations.CreateModel(
            name="PerformancePrice",
            fields=[
                ("id", models.BigAutoField(auto_created=True, primary_key=True, serialize=False, verbose_name="ID")),
                ("label", models.CharField(help_text="좌석/권종명", max_length=100)),
                ("price", models.PositiveIntegerField(help_text="가격")),
                ("currency", models.CharField(default="KRW", help_text="통화", max_length=10)),
                ("raw_text", models.CharField(blank=True, help_text="파싱에 사용한 원문 조각", max_length=255)),
                ("sort_order", models.PositiveSmallIntegerField(default=0, help_text="정렬 순서")),
                (
                    "performance",
                    models.ForeignKey(
                        help_text="공연 FK",
                        on_delete=django.db.models.deletion.CASCADE,
                        related_name="price_options",
                        to="performances.performance",
                    ),
                ),
            ],
            options={
                "verbose_name": "공연 가격",
                "verbose_name_plural": "공연 가격 목록",
                "db_table": "performance_prices",
                "ordering": ["sort_order", "id"],
            },
        ),
        migrations.AddIndex(
            model_name="performanceprice",
            index=models.Index(fields=["price"], name="performance_price_9cc2ec_idx"),
        ),
        migrations.AddIndex(
            model_name="performanceprice",
            index=models.Index(fields=["label"], name="performance_label_437f98_idx"),
        ),
    ]
