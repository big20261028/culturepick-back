from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display = ("email", "nickname", "provider", "status", "is_admin", "created_at")
    list_filter = ("provider", "status", "is_admin")
    search_fields = ("email", "nickname")
    ordering = ("-created_at",)

    fieldsets = (
        (None, {"fields": ("email", "password")}),
        ("Info", {"fields": ("nickname", "phone", "provider", "provider_id")}),
        ("Status", {"fields": ("status", "is_admin", "is_staff", "is_superuser")}),
        ("Permissions", {"fields": ("groups", "user_permissions")}),
    )
    add_fieldsets = (
        (None, {
            "classes": ("wide",),
            "fields": ("email", "password1", "password2"),
        }),
    )