import re

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.contrib.auth.tokens import default_token_generator
from django.db import transaction
from django.utils import timezone
from django.utils.encoding import force_str
from django.utils.http import urlsafe_base64_decode
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed

User = get_user_model()

EMAIL_PATTERN = re.compile(r"^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$")
EMOJI_PATTERN = re.compile(r"[\U0001F300-\U0001FAFF]")
SPECIAL_PASSWORD_PATTERN = re.compile(r"""[!@#$%^&*(),.?":{}|<>]""")


def validate_frontend_email(value):
    email = value.strip()

    if not email:
        raise serializers.ValidationError("Email is required.")

    if "@" not in email:
        raise serializers.ValidationError("Email must include @.")

    if EMOJI_PATTERN.search(email):
        raise serializers.ValidationError("Email cannot include emoji.")

    if not EMAIL_PATTERN.fullmatch(email):
        raise serializers.ValidationError("Enter a valid email address.")

    return email


def validate_frontend_password(value):
    errors = []

    if len(value) < 8:
        errors.append("Password must be at least 8 characters.")

    if not re.search(r"[A-Za-z]", value):
        errors.append("Password must include at least one letter.")

    if not re.search(r"\d", value):
        errors.append("Password must include at least one number.")

    if not SPECIAL_PASSWORD_PATTERN.search(value):
        errors.append("Password must include at least one special character.")

    if errors:
        raise serializers.ValidationError(errors)

    return value


def user_display_name(user):
    nickname = (getattr(user, "nickname", "") or "").strip()
    return nickname or getattr(user, "email", "")


class LocalSignupSerializer(serializers.ModelSerializer):
    email = serializers.CharField()
    password = serializers.CharField(write_only=True, style={"input_type": "password"})
    password_confirm = serializers.CharField(write_only=True, style={"input_type": "password"})
    nickname = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ("email", "password", "password_confirm", "nickname")

    def validate_email(self, value):
        email = validate_frontend_email(value)
        if User.objects.filter(email__iexact=email).exists():
            raise serializers.ValidationError("Email is already registered.")
        return email

    def validate_password(self, value):
        validate_frontend_password(value)
        validate_password(value)
        return value

    def validate(self, data):
        if data["password"] != data["password_confirm"]:
            raise serializers.ValidationError({"password": "Passwords do not match."})
        return data

    def create(self, validated_data):
        validated_data.pop("password_confirm")
        return User.objects.create_user(
            email=validated_data["email"],
            password=validated_data["password"],
            nickname=validated_data.get("nickname", ""),
        )


class LocalLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data.get("email")
        password = data.get("password")

        if not email or not password:
            raise serializers.ValidationError("Email and password are required.")

        user = authenticate(email=email, password=password)

        if not user:
            raise AuthenticationFailed("Invalid email or password.")

        if not user.is_active:
            raise AuthenticationFailed("This account is inactive.")

        data["user"] = user
        return data


class SocialAuthSerializer(serializers.Serializer):
    provider = serializers.CharField(max_length=10)
    code = serializers.CharField()
    redirect_uri = serializers.CharField()
    state = serializers.CharField(required=False, allow_blank=True)


class AccountEmailSerializer(serializers.Serializer):
    email = serializers.CharField(max_length=254)

    def validate_email(self, value):
        return validate_frontend_email(value)


class PasswordResetConfirmSerializer(serializers.Serializer):
    uid = serializers.CharField(max_length=128, write_only=True)
    token = serializers.CharField(max_length=256, write_only=True)
    new_password = serializers.CharField(write_only=True, style={"input_type": "password"})
    new_password_confirm = serializers.CharField(write_only=True, style={"input_type": "password"})

    invalid_token_message = "The password reset link is invalid or has expired."

    def validate(self, attrs):
        try:
            user_id = force_str(urlsafe_base64_decode(attrs["uid"]))
            user = User.objects.get(pk=user_id)
        except (TypeError, ValueError, OverflowError, UnicodeDecodeError, User.DoesNotExist):
            raise serializers.ValidationError({"token": self.invalid_token_message}) from None

        is_resettable_local_account = (
            user.is_active
            and user.provider == User.Provider.LOCAL
            and user.has_usable_password()
        )
        if not is_resettable_local_account or not default_token_generator.check_token(user, attrs["token"]):
            raise serializers.ValidationError({"token": self.invalid_token_message})

        if attrs["new_password"] != attrs["new_password_confirm"]:
            raise serializers.ValidationError({"new_password_confirm": "New passwords do not match."})

        validate_frontend_password(attrs["new_password"])
        validate_password(attrs["new_password"], user)
        attrs["user"] = user
        return attrs

    def save(self, **kwargs):
        from .recovery import reset_local_user_password

        token = self.validated_data["token"]
        with transaction.atomic():
            try:
                user = User.objects.select_for_update().get(pk=self.validated_data["user"].pk)
            except User.DoesNotExist:
                raise serializers.ValidationError({"token": self.invalid_token_message}) from None
            is_resettable_local_account = (
                user.is_active
                and user.provider == User.Provider.LOCAL
                and user.has_usable_password()
            )
            # The row lock plus a fresh token check prevents concurrent reuse.
            if not is_resettable_local_account or not default_token_generator.check_token(user, token):
                raise serializers.ValidationError({"token": self.invalid_token_message})

            reset_local_user_password(user, self.validated_data["new_password"])
        return user


class PasswordVerificationSerializer(serializers.Serializer):
    password = serializers.CharField(write_only=True, style={"input_type": "password"})

    def validate_password(self, value):
        user = self.context["request"].user

        if not user.has_usable_password():
            raise serializers.ValidationError("This account does not use a local password.")

        if not user.check_password(value):
            raise serializers.ValidationError("Password does not match.")

        return value


class UserProfileSerializer(serializers.ModelSerializer):
    display_name = serializers.SerializerMethodField()
    can_change_password = serializers.SerializerMethodField()
    requires_password_verification = serializers.SerializerMethodField()
    new_password = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        style={"input_type": "password"},
    )
    new_password_confirm = serializers.CharField(
        write_only=True,
        required=False,
        allow_blank=True,
        style={"input_type": "password"},
    )

    class Meta:
        model = User
        fields = (
            "email",
            "nickname",
            "display_name",
            "phone",
            "provider",
            "created_at",
            "updated_at",
            "can_change_password",
            "requires_password_verification",
            "new_password",
            "new_password_confirm",
        )
        read_only_fields = (
            "email",
            "display_name",
            "provider",
            "created_at",
            "updated_at",
            "can_change_password",
            "requires_password_verification",
        )

    def get_display_name(self, obj):
        return user_display_name(obj)

    def get_can_change_password(self, obj):
        return obj.has_usable_password()

    def get_requires_password_verification(self, obj):
        return obj.has_usable_password()

    def validate(self, attrs):
        password = attrs.get("new_password")
        password_confirm = attrs.get("new_password_confirm")
        password_keys_present = "new_password" in attrs or "new_password_confirm" in attrs

        if password_keys_present and not password and not password_confirm:
            attrs.pop("new_password", None)
            attrs.pop("new_password_confirm", None)
            return attrs

        if password_keys_present:
            if self.instance and not self.instance.has_usable_password():
                raise serializers.ValidationError(
                    {"new_password": "Social login accounts cannot change password here."}
                )

            if not password or not password_confirm:
                raise serializers.ValidationError(
                    {"new_password": "Both new_password and new_password_confirm are required."}
                )

            if password != password_confirm:
                raise serializers.ValidationError({"new_password_confirm": "New passwords do not match."})

            validate_frontend_password(password)
            validate_password(password, self.instance)

        return attrs

    def update(self, instance, validated_data):
        from .recovery import change_user_password_and_revoke_sessions

        new_password = validated_data.pop("new_password", None)
        validated_data.pop("new_password_confirm", None)

        with transaction.atomic():
            current = User.objects.select_for_update().get(pk=instance.pk)
            for field, value in validated_data.items():
                setattr(current, field, value)

            update_fields = set(validated_data)
            if new_password:
                change_user_password_and_revoke_sessions(
                    current,
                    new_password,
                    additional_update_fields=update_fields,
                )
            elif update_fields:
                current.updated_at = timezone.now()
                current.save(update_fields=update_fields | {"updated_at"})

        return current
