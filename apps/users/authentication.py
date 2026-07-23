from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.authentication import JWTAuthentication


LEGACY_AUTH_VERSION = 1


def get_token_auth_version(validated_token):
    """Return the token version, treating pre-deployment tokens as version 1."""
    value = validated_token.get("auth_version", LEGACY_AUTH_VERSION)
    if isinstance(value, bool) or not isinstance(value, int) or value < 1:
        return None
    return value


class AuthVersionJWTAuthentication(JWTAuthentication):
    """Reject JWTs issued before the user's latest security transition."""

    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        token_version = get_token_auth_version(validated_token)

        if token_version is None or token_version != user.auth_version:
            raise AuthenticationFailed(
                "This token has been revoked. Please sign in again.",
                code="token_revoked",
            )

        return user
