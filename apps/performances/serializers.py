'''
DB에 데이터를 넣거나 바꿀 때 (가입, 글쓰기, 수정): ModelSerializer

DB와 상관없이 일회성 데이터만 검증할 때 (로그인, 비밀번호 초기화 메일 발송, 필터 검색어 검증): serializers.Serializer
'''

from rest_framework import serializers
from django.contrib.auth import authenticate
from rest_framework.exceptions import AuthenticationFailed
from django.contrib.auth import get_user_model

User = get_user_model()

# 일반 회원가입 시리얼라이저
class LocalSignupSerializer(serializers.ModelSerializer):
    password = serializers.CharField(write_only=True, style={'input_type':'password'})
    password_confirm = serializers.CharField(write_only=True, style={'input_type' : 'password'})
    nickname = serializers.CharField(required=True)

    class Meta:
        model = User
        fields = ('email', 'password', 'password_confirm', 'nickname',)

    def validate(self, data):
        if data['password'] != data['password_confirm']:
            raise serializers.ValidationError({'password': '비밀번호가 일치하지 않습니다.'})
        return data

    def create(self, validated_data):
        validated_data.pop('password_confirm')
        
        user = User.objects.create_user(
            email=validated_data['email'],
            password=validated_data['password'],
            nickname=validated_data['nickname'],
        )
        return user