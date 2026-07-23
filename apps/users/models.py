from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.core.exceptions import ValidationError
from django.db import models
from django.utils import timezone


class UserManager(BaseUserManager):
    def create_user(self, email, password=None, **extra_fields):
        if not email:
            raise ValueError("email is required")
        email = self.normalize_email(email)
        user = self.model(email=email, **extra_fields)
        user.set_password(password)
        user.save(using=self._db)
        return user

    def create_superuser(self, email, password=None, **extra_fields):
        extra_fields.setdefault("is_staff", True)
        extra_fields.setdefault("is_superuser", True)
        extra_fields.setdefault("is_admin", True)
        return self.create_user(email, password, **extra_fields)


class User(AbstractBaseUser, PermissionsMixin):

    class Provider(models.TextChoices):
        LOCAL = "local", "local"
        GOOGLE = "google", "google"
        KAKAO = "kakao", "kakao"
        NAVER = "naver", "naver"

    class Status(models.IntegerChoices):
        ACTIVE = 1, "active"
        INACTIVE = 0, "inactive"
        BANNED = 2, "banned"

    class DeactivationReason(models.TextChoices):
        SELF_DEACTIVATED = "self_deactivated", "User self-deactivated"
        ADMIN_DISABLED = "admin_disabled", "Disabled by administrator"
        SECURITY_LOCK = "security_lock", "Security lock"
        POLICY_BANNED = "policy_banned", "Policy ban"

    INACTIVE_REASONS = {
        DeactivationReason.SELF_DEACTIVATED,
        DeactivationReason.ADMIN_DISABLED,
        DeactivationReason.SECURITY_LOCK,
    }

    email = models.EmailField(unique=True)
    nickname = models.CharField(max_length=50, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    provider = models.CharField(max_length=10, choices=Provider.choices, default=Provider.LOCAL)
    provider_id = models.CharField(max_length=255, blank=True)
    refresh_token = models.CharField(max_length=512, blank=True)
    refresh_token_expires_at = models.DateTimeField(null=True, blank=True)
    auth_version = models.PositiveIntegerField(default=1, editable=False)
    status = models.IntegerField(choices=Status.choices, default=Status.ACTIVE)
    deactivation_reason = models.CharField(
        max_length=32,
        choices=DeactivationReason.choices,
        blank=True,
        default="",
    )
    deactivated_at = models.DateTimeField(null=True, blank=True)
    is_admin = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "users"
        constraints = [
            models.CheckConstraint(
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
        ]

    def __str__(self):
        return self.email

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE

    @property
    def can_recover_self_deactivated_account(self):
        return (
            self.status == self.Status.INACTIVE
            and self.deactivation_reason == self.DeactivationReason.SELF_DEACTIVATED
        )

    def _normalize_account_state(self):
        changed_fields = set()

        if self.status == self.Status.ACTIVE:
            if self.deactivation_reason:
                self.deactivation_reason = ""
                changed_fields.add("deactivation_reason")
            if self.deactivated_at is not None:
                self.deactivated_at = None
                changed_fields.add("deactivated_at")
            return changed_fields

        if self.status == self.Status.BANNED:
            if self.deactivation_reason != self.DeactivationReason.POLICY_BANNED:
                self.deactivation_reason = self.DeactivationReason.POLICY_BANNED
                changed_fields.add("deactivation_reason")
        elif self.status == self.Status.INACTIVE:
            if not self.deactivation_reason:
                # Unknown legacy/admin state must default to a protected reason.
                self.deactivation_reason = self.DeactivationReason.ADMIN_DISABLED
                changed_fields.add("deactivation_reason")
            elif self.deactivation_reason not in self.INACTIVE_REASONS:
                raise ValidationError(
                    {"deactivation_reason": "Invalid reason for an inactive account."}
                )

        if self.deactivated_at is None:
            self.deactivated_at = timezone.now()
            changed_fields.add("deactivated_at")

        return changed_fields

    def clean(self):
        super().clean()
        self._normalize_account_state()

    def save(self, *args, **kwargs):
        previous = None
        if self.pk:
            previous = (
                type(self)
                .objects.filter(pk=self.pk)
                .values("status", "auth_version")
                .first()
            )

        normalized_fields = self._normalize_account_state()
        status_changed = previous is not None and previous["status"] != self.status
        if status_changed:
            # A status transition must never make a previously issued token
            # valid again if the account is later reactivated.
            self.auth_version = max(self.auth_version, previous["auth_version"] + 1)
            self.refresh_token = ""
            self.refresh_token_expires_at = None
            normalized_fields.update(
                {"auth_version", "refresh_token", "refresh_token_expires_at"}
            )

        update_fields = kwargs.get("update_fields")
        if update_fields is not None and (normalized_fields or status_changed):
            kwargs["update_fields"] = set(update_fields) | normalized_fields | {
                "status",
                "deactivation_reason",
                "deactivated_at",
            }

        return super().save(*args, **kwargs)

    def deactivate(self, *, reason=DeactivationReason.SELF_DEACTIVATED):
        if reason not in self.INACTIVE_REASONS:
            raise ValidationError(
                {"deactivation_reason": "Invalid reason for an inactive account."}
            )
        self.status = self.Status.INACTIVE
        self.deactivation_reason = reason
        self.deactivated_at = timezone.now()
        self.save(
            update_fields=[
                "status",
                "deactivation_reason",
                "deactivated_at",
                "updated_at",
            ]
        )

    def ban(self):
        self.status = self.Status.BANNED
        self.deactivation_reason = self.DeactivationReason.POLICY_BANNED
        self.deactivated_at = timezone.now()
        self.save(
            update_fields=[
                "status",
                "deactivation_reason",
                "deactivated_at",
                "updated_at",
            ]
        )

    def recover_self_deactivated_account(self):
        if not self.can_recover_self_deactivated_account:
            raise ValidationError(
                "Only accounts explicitly deactivated by their owner can be recovered."
            )
        self.status = self.Status.ACTIVE
        self.deactivation_reason = ""
        self.deactivated_at = None
        self.save(
            update_fields=[
                "status",
                "deactivation_reason",
                "deactivated_at",
                "updated_at",
            ]
        )
