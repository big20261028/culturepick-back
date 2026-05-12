from django.db import models

# Create your models here.
from django.contrib.auth.models import AbstractBaseUser, BaseUserManager, PermissionsMixin
from django.db import models


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

    email = models.EmailField(unique=True)
    nickname = models.CharField(max_length=50, blank=True)
    phone = models.CharField(max_length=20, blank=True)
    provider = models.CharField(max_length=10, choices=Provider.choices, default=Provider.LOCAL)
    provider_id = models.CharField(max_length=255, blank=True)
    refresh_token = models.CharField(max_length=512, blank=True)
    refresh_token_expires_at = models.DateTimeField(null=True, blank=True)
    status = models.IntegerField(choices=Status.choices, default=Status.ACTIVE)
    is_admin = models.BooleanField(default=False)
    is_staff = models.BooleanField(default=False)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    objects = UserManager()

    USERNAME_FIELD = "email"
    REQUIRED_FIELDS = []

    class Meta:
        db_table = "users"

    def __str__(self):
        return self.email

    @property
    def is_active(self):
        return self.status == self.Status.ACTIVE