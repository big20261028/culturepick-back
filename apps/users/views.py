from django.shortcuts import render

from rest_framework.decorators import api_view, permission_classes
from rest_framework.permissions import AllowAny
from rest_framework.response import Response
from rest_framework import status

from rest_framework_simplejwt.tokens import RefreshToken
from rest_framework_simplejwt.views import TokenRefreshView
from rest_framework_simplejwt.exceptions import InvalidToken

from .serializers import LocalLoginSerializer,LocalSignupSerializer,SocialAuthSerializer

from django.contrib.auth import login as auth_login
from django.contrib.auth import logout as auth_logout
from django.contrib.auth import get_user_model

User = get_user_model()


# Create your views here.
@api_view(['POST'])
@permission_classes([AllowAny])
def login(request):
    serializer = LocalLoginSerializer(data=request.data)
    if serializer.is_valid(raise_exception=True):
        user = serializer.validated_data['user']
        # auth_login(request, serializer.user)  <=  세션을 이용하는 방식
        refresh = RefreshToken.for_user(user)

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