from django.contrib.auth import get_user_model
from django.core import signing
from django.db.models import Count, IntegerField, Prefetch, Q, Value
from rest_framework import generics
from rest_framework.exceptions import ValidationError
from rest_framework import status
from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.exceptions import InvalidToken
from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView

from apps.performances.models import Performance, UsersPerformanceAction
from apps.performances.serializers import PerformanceListSerializer
from apps.community.models import Post, normalize_post_category
from apps.community.serializers import PostSerializer

from .serializers import (
    LocalLoginSerializer,
    LocalSignupSerializer,
    PasswordVerificationSerializer,
    SocialAuthSerializer,
    UserProfileSerializer,
)
from .services import get_google_info, get_kakao_info, get_naver_info

User = get_user_model()

PROFILE_UPDATE_TOKEN_MAX_AGE_SECONDS = 10 * 60
PROFILE_UPDATE_TOKEN_SALT = "users.profile_update"

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


def _make_profile_update_token(user):
    return signing.TimestampSigner(salt=PROFILE_UPDATE_TOKEN_SALT).sign(str(user.pk))


def _is_valid_profile_update_token(user, token):
    if not token:
        return False

    try:
        value = signing.TimestampSigner(salt=PROFILE_UPDATE_TOKEN_SALT).unsign(
            token,
            max_age=PROFILE_UPDATE_TOKEN_MAX_AGE_SECONDS,
        )
    except signing.BadSignature:
        return False

    return value == str(user.pk)


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


class MyPerformanceActionListView(APIView):
    permission_classes = [IsAuthenticated]
    action_type = None
    response_type = ""

    def get_queryset(self):
        user_actions = UsersPerformanceAction.objects.filter(user=self.request.user)
        return (
            Performance.objects.filter(
                users_performance_actions__user=self.request.user,
                users_performance_actions__action_type=self.action_type,
            )
            .select_related("venue")
            .prefetch_related(
                "price_options",
                Prefetch(
                    "users_performance_actions",
                    queryset=user_actions,
                    to_attr="current_user_actions",
                )
            )
            .annotate(search_score=Value(0, output_field=IntegerField()))
            .order_by("-users_performance_actions__created_at", "title", "performance_id")
        )

    def get(self, request):
        serializer = PerformanceListSerializer(
            self.get_queryset(),
            many=True,
            context={"request": request},
        )
        return Response(
            {
                "type": self.response_type,
                "total": len(serializer.data),
                "results": serializer.data,
            },
            status=status.HTTP_200_OK,
        )


class MyInterestPerformanceListView(MyPerformanceActionListView):
    action_type = UsersPerformanceAction.ActionType.INTEREST
    response_type = "interest"


class MyWatchlistPerformanceListView(MyPerformanceActionListView):
    action_type = UsersPerformanceAction.ActionType.WATCHLIST
    response_type = "watchlist"


class MyCommunityPostListView(generics.ListAPIView):
    permission_classes = [IsAuthenticated]
    serializer_class = PostSerializer

    def get_queryset(self):
        queryset = (
            Post.objects.filter(author=self.request.user)
            .select_related("author")
            .annotate(comment_count=Count("comments"))
            .order_by("-created_at", "-id")
        )

        category_param = (
            self.request.query_params.get("category")
            or self.request.query_params.get("category_slug")
            or ""
        )
        category = normalize_post_category(category_param)
        if category is None:
            raise ValidationError({"category": "Invalid category."})
        if category:
            queryset = queryset.filter(category=category)

        keyword = (
            self.request.query_params.get("keyword")
            or self.request.query_params.get("search")
            or self.request.query_params.get("q")
            or ""
        ).strip()
        if keyword:
            queryset = queryset.filter(Q(title__icontains=keyword) | Q(content__icontains=keyword))

        return queryset


class MyProfileView(APIView):
    permission_classes = [IsAuthenticated]

    def get(self, request):
        return Response(UserProfileSerializer(request.user).data, status=status.HTTP_200_OK)

    def patch(self, request):
        verification_token = request.data.get("verification_token")
        if request.user.has_usable_password() and not _is_valid_profile_update_token(request.user, verification_token):
            return Response(
                {"verification_token": "A valid profile update verification token is required."},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = UserProfileSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()
        return Response(serializer.data, status=status.HTTP_200_OK)


class MyPasswordVerificationView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request):
        serializer = PasswordVerificationSerializer(data=request.data, context={"request": request})
        serializer.is_valid(raise_exception=True)
        return Response(
            {
                "verified": True,
                "verification_token": _make_profile_update_token(request.user),
                "expires_in": PROFILE_UPDATE_TOKEN_MAX_AGE_SECONDS,
            },
            status=status.HTTP_200_OK,
        )
