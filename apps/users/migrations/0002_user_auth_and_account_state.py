from django.db import migrations, models
from django.utils import timezone


def classify_existing_inactive_accounts(apps, schema_editor):
    User = apps.get_model("users", "User")
    now = timezone.now()

    for user in User.objects.filter(status__in=[0, 2]).iterator(chunk_size=1000):
        user.deactivated_at = user.updated_at or now
        if user.status == 2:
            user.deactivation_reason = "policy_banned"
        else:
            # An unknown legacy inactive account must not become eligible for
            # automatic recovery. Treat it as administratively disabled.
            user.deactivation_reason = "admin_disabled"
        user.save(
            update_fields=[
                "deactivation_reason",
                "deactivated_at",
            ]
        )


class Migration(migrations.Migration):
    dependencies = [
        ("users", "0001_initial"),
    ]

    operations = [
        migrations.AddField(
            model_name="user",
            name="auth_version",
            field=models.PositiveIntegerField(default=1, editable=False),
        ),
        migrations.AddField(
            model_name="user",
            name="deactivation_reason",
            field=models.CharField(
                blank=True,
                choices=[
                    ("self_deactivated", "User self-deactivated"),
                    ("admin_disabled", "Disabled by administrator"),
                    ("security_lock", "Security lock"),
                    ("policy_banned", "Policy ban"),
                ],
                default="",
                max_length=32,
            ),
        ),
        migrations.AddField(
            model_name="user",
            name="deactivated_at",
            field=models.DateTimeField(blank=True, null=True),
        ),
        migrations.RunPython(
            classify_existing_inactive_accounts,
            migrations.RunPython.noop,
        ),
        migrations.AddConstraint(
            model_name="user",
            constraint=models.CheckConstraint(
                condition=(
                    models.Q(
                        status=1,
                        deactivation_reason="",
                        deactivated_at__isnull=True,
                    )
                    | models.Q(
                        status=0,
                        deactivation_reason__in=[
                            "self_deactivated",
                            "admin_disabled",
                            "security_lock",
                        ],
                        deactivated_at__isnull=False,
                    )
                    | models.Q(
                        status=2,
                        deactivation_reason="policy_banned",
                        deactivated_at__isnull=False,
                    )
                ),
                name="users_account_state_consistent",
            ),
        ),
    ]
