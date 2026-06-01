from django.contrib.auth import get_user_model
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from .serializers import LocalLoginSerializer, LocalSignupSerializer, SocialAuthSerializer
from .services import get_google_info, get_kakao_info, get_naver_info

User = get_user_model()

SOCIAL_AUTH_STRATEGIES = {
    "kakao": get_kakao_info,
    "naver": get_naver_info,
    "google": get_google_info,
}

PROVIDER_MAP = {
    "kakao": User.Provider.KAKAO,
    "naver": User.Provider.NAVER,
    "google": User.Provider.GOOGLE,
}


def _issue_tokens(user):
    refresh = RefreshToken.for_user(user)
    user.refresh_token = str(refresh)
    user.save(update_fields=["refresh_token"])
    return {
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }


@api_view(["POST"])
@permission_classes([AllowAny])
def login(request):
    serializer = LocalLoginSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    return Response(_issue_tokens(serializer.validated_data["user"]), status=status.HTTP_200_OK)


@api_view(["POST"])
def logout(request):
    refresh_token = request.data.get("refresh")
    if not refresh_token:
        return Response({"message": "리프레시 토큰이 필요합니다."}, status=status.HTTP_400_BAD_REQUEST)

    try:
        token = RefreshToken(refresh_token)
        token.blacklist()

        request.user.refresh_token = ""
        request.user.save(update_fields=["refresh_token"])

        return Response({"message": "로그아웃 되었습니다."}, status=status.HTTP_200_OK)
    except Exception:
        return Response({"message": "유효하지 않은 토큰입니다."}, status=status.HTTP_400_BAD_REQUEST)


@api_view(["POST"])
@permission_classes([AllowAny])
def register(request):
    serializer = LocalSignupSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    serializer.save()
    return Response({"message": "회원가입이 완료되었습니다."}, status=status.HTTP_201_CREATED)


class CustomTokenRefreshView(TokenRefreshView):
    permission_classes = [AllowAny]

    def post(self, request, *args, **kwargs):
        refresh_token = request.data.get("refresh")
        user = User.objects.filter(refresh_token=refresh_token).first()

        if not user:
            raise InvalidToken("유효하지 않거나 이미 폐기된 jwt 리프레시 토큰입니다.")

        response = super().post(request, *args, **kwargs)

        new_refresh = response.data.get("refresh")
        if new_refresh:
            user.refresh_token = new_refresh
            user.save(update_fields=["refresh_token"])

        return response


@api_view(["POST"])
@permission_classes([AllowAny])
def social_login(request):
    serializer = SocialAuthSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)

    provider = serializer.validated_data["provider"]
    strategy_func = SOCIAL_AUTH_STRATEGIES.get(provider)
    provider_value = PROVIDER_MAP.get(provider)

    if not strategy_func or not provider_value:
        return Response({"detail": "지원하지 않는 소셜 로그인입니다."}, status=status.HTTP_400_BAD_REQUEST)

    code = serializer.validated_data["code"]
    redirect_uri = serializer.validated_data["redirect_uri"]
    state = serializer.validated_data.get("state", "")

    if provider == "naver":
        user_info = strategy_func(code, state)
    else:
        user_info = strategy_func(code, redirect_uri)

    user, created = User.objects.get_or_create(
        email=user_info["email"],
        defaults={
            "provider": provider_value,
            "provider_id": user_info["provider_id"],
            "nickname": user_info.get("nickname", ""),
        },
    )

    if not created and user.provider != provider_value:
        return Response(
            {"detail": f"이 이메일은 이미 {user.provider}로 가입되어 있습니다."},
            status=status.HTTP_400_BAD_REQUEST,
        )

    if created:
        user.set_unusable_password()
        user.save(update_fields=["password"])
    elif user.provider_id and user.provider_id != user_info["provider_id"]:
        return Response(
            {"detail": "소셜 계정 정보가 기존 가입 정보와 일치하지 않습니다."},
            status=status.HTTP_400_BAD_REQUEST,
        )
    elif not user.provider_id:
        user.provider_id = user_info["provider_id"]
        user.save(update_fields=["provider_id"])

    message = "회원가입 완료" if created else "로그인 성공"
    return Response({"message": message, **_issue_tokens(user)}, status=status.HTTP_200_OK)
