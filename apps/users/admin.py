from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = (
        "email",
        "nickname",
        "provider",
        "status",
        "deactivation_reason",
        "is_admin",
        "created_at",
    )
    list_filter = ("provider", "status", "deactivation_reason", "is_admin")
    search_fields = ("email", "nickname")
    ordering = ("-created_at",)
    readonly_fields = ("auth_version", "deactivated_at", "created_at", "updated_at")

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Info", {"fields": ("nickname", "phone", "provider", "provider_id")}),
        (
            "Status",
            {
                "fields": (
                    "status",
                    "deactivation_reason",
                    "deactivated_at",
                    "auth_version",
                    "is_admin",
                    "is_staff",
                    "is_superuser",
                )
            },
        ),
        ("Permissions", {"fields": ("groups", "user_permissions")}),
        ("Timestamps", {"fields": ("created_at", "updated_at")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "password1", "password2"),
        }),
    )
