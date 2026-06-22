import re

from django.contrib.auth import authenticate, get_user_model
from django.contrib.auth.password_validation import validate_password
from django.utils import timezone
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
        return validate_frontend_email(value)

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
        new_password = validated_data.pop("new_password", None)
        validated_data.pop("new_password_confirm", None)

        for field, value in validated_data.items():
            setattr(instance, field, value)

        update_fields = list(validated_data.keys())
        if new_password:
            instance.set_password(new_password)
            update_fields.append("password")

        if update_fields:
            instance.updated_at = timezone.now()
            update_fields.append("updated_at")
            instance.save(update_fields=update_fields)

        return instance
