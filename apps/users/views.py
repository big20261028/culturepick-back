from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.exceptions import InvalidToken

from .serializers import LocalLoginSerializer,LocalSignupSerializer,SocialAuthSerializer
from .services import get_google_info, get_kakao_info, get_naver_info

from django.contrib.auth import get_user_model

User = get_user_model()

SOCIAL_AUTH_STRATEGIES = {
    "kakao": get_kakao_info,
    "naver": get_naver_info,
    "google": get_google_info,
}
PROVIDER_MAP = {
    'kakao': User.Provider.KAKAO,
    'naver': User.Provider.NAVER,
    'google': User.Provider.GOOGLE,
}

# Create your views here.
@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    serializer = LocalLoginSerializer(data=request.data)
    if serializer.is_valid(raise_exception=True):
        user = serializer.validated_data['user']
        # auth_login(request, serializer.user)  <=  세션을 이용하는 방식
        refresh = RefreshToken.for_user(user)

        # refresh_token DB 저장 추가
        user.refresh_token = str(refresh)
        user.save(update_fields=['refresh_token'])

        return Response({
            'access': str(refresh.access_token),
            'refresh' : str(refresh),
        }, status=status.HTTP_200_OK) 

@api_view(['POST'])
def logout(request):
    refresh_token = request.data.get('refresh')
    if not refresh_token: # 로그인 되어 있지 않음
        return Response(
            {'message' : '리프레시 토큰이 필요합니다.'},
            status = status.HTTP_400_BAD_REQUEST
        )
    try:
        token = RefreshToken(refresh_token)
        token.blacklist()

        request.user.refresh_token = ''
        request.user.save(update_fields=['refresh_token'])

        return Response(
            {"message":'로그아웃 되었습니다.'},
            status=status.HTTP_200_OK
        )
    except Exception:
        return Response(
            {'message':'유효하지 않은 토큰입니다.'},
            status = status.HTTP_400_BAD_REQUEST
        )

@api_view(['POST'])    
@permission_classes([AllowAny])
def register(request):
    serializer = LocalSignupSerializer(data=request.data)
    if serializer.is_valid(raise_exception=True):
        # user = serializer.validated_data['user']
        # User.objects.create_user(user)
        user = serializer.save()
        return Response({
            'message' : '회원가입이 완료되었습니다.'
        }, status=status.HTTP_201_CREATED)
        
# DB에 등록된 리프레시 토큰과 추가 검증하는 로직
class CustomTokenRefreshView(TokenRefreshView):
    permission_classes = [AllowAny]
    def post(self, request, *args, **kwargs):
        refresh_token = request.data.get('refresh')
        user = User.objects.filter(refresh_token=refresh_token).first()

        if not user:
            raise InvalidToken('유효하지 않거나 이미 폐기된 jwt 리프레시 토큰입니다.')

        response = super().post(request, *args, **kwargs)

        new_refresh = response.data.get('refresh')
        if new_refresh:
            user.refresh_token = new_refresh
            user.save(update_fields=['refresh_token'])

        return response
    
@api_view(['POST'])
@permission_classes([AllowAny])
def social_login(request):
    # 1. 프론트엔드가 보낸 데이터 검증
    serializer = SocialAuthSerializer(data=request.data)
    serializer.is_valid(raise_exception=True)
    
    provider = serializer.validated_data['provider']
    code = serializer.validated_data['code']
    redirect_uri = serializer.validated_data['redirect_uri']
    state = serializer.validated_data.get('state', '') 
    
    # 네이버는 state, 나머지는 redirect_uri
    if provider == 'naver':
        user_info = strategy_func(code, state)
    else:
        user_info = strategy_func(code, redirect_uri)

    # 1. 딕셔너리에서 담당 함수 꺼내기
    strategy_func = SOCIAL_AUTH_STRATEGIES.get(provider)
    if not strategy_func:
        return Response({"detail": "지원하지 않는 소셜 로그인입니다."}, status=status.HTTP_400_BAD_REQUEST)
        
    # 3. DB에서 유저를 찾거나 새로 만듭니다 (가입 & 로그인 동시 처리)
    user, created = User.objects.get_or_create(
        email=user_info['email'],
        defaults={
            'provider': PROVIDER_MAP.get(provider),
            'provider_id': user_info['provider_id'],
            'nickname': user_info['nickname'],
            # 비밀번호는 없으므로 랜덤값이나 None 처리 (User 모델 설정에 따라)
        }
    )
    
    # (선택) 기존 로컬 가입자가 카카오로 로그인 시도하는 경우 방어 로직
    if not created and user.provider != PROVIDER_MAP.get(provider):
        return Response({"detail": f"이 이메일은 이미 {user.provider}로 가입되어 있습니다."}, status=status.HTTP_400_BAD_REQUEST)
    
    # 4. 우리 서버만의 고유 JWT 토큰 발행
    refresh = RefreshToken.for_user(user)
    
    # (선택) refresh_token을 DB에 저장하기로 했으므로 업데이트
    user.refresh_token = str(refresh)
    user.save()
    
    return Response({
        "message": "회원가입 완료" if created else "로그인 성공",
        "access": str(refresh.access_token),
        "refresh": str(refresh),
    }, status=status.HTTP_200_OK)