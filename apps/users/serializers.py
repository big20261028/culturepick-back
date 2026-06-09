'''
DB에 데이터를 넣거나 바꿀 때 (가입, 글쓰기, 수정): ModelSerializer

DB와 상관없이 일회성 데이터만 검증할 때 (로그인, 비밀번호 초기화 메일 발송, 필터 검색어 검증): serializers.Serializer
'''

from rest_framework import serializers
from django.contrib.auth import authenticate
from django.contrib.auth.password_validation import validate_password
from rest_framework.exceptions import AuthenticationFailed
from django.contrib.auth import get_user_model

User = get_user_model()

# 일반 회원가입 시리얼라이저
class LocalSignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={'input_type':'password'})
    password_confirm = serializers.CharField(write_only=True, style={'input_type' : 'password'})
    nickname = serializers.CharField(required=False, allow_blank=True)

    class Meta:
        model = User
        fields = ('email', 'password', 'password_confirm', 'nickname',)

    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError({'password': '비밀번호가 일치하지 않습니다.'})
        validate_password(data['password'])
        return data

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            nickname=validated_data.get('nickname', ''),
        )
        return user

# 일반 로그인 시리얼라이저
class LocalLoginSerializer(serializers.Serializer):
    email = serializers.EmailField()
    password = serializers.CharField(write_only=True)

    def validate(self, data):
        email = data.get('email')
        password = data.get('password')

        if not email or not password:
            raise serializers.ValidationError('이메일과 비밀번호를 모두 입력해주세요.')

        user = authenticate(email=email, password=password)

        if not user:
            raise AuthenticationFailed('이메일 또는 비밀번호가 잘못되었습니다.')
        
        if not user.is_active:
            raise AuthenticationFailed('정지되거나 탈퇴한 계정입니다.')
        
        data['user'] = user

        return data

# 소셜(Oauth) 전용 시리얼라이저
class SocialAuthSerializer(serializers.Serializer):
    provider = serializers.CharField(max_length=10)
    code = serializers.CharField()
    redirect_uri = serializers.CharField()   # 네이버는 state도 추가 필요
    state = serializers.CharField(required=False, allow_blank=True)  # 네이버 전용
