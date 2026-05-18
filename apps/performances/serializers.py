'''
DB에 데이터를 넣거나 바꿀 때 (가입, 글쓰기, 수정): ModelSerializer

DB와 상관없이 일회성 데이터만 검증할 때 (로그인, 비밀번호 초기화 메일 발송, 필터 검색어 검증): serializers.Serializer
'''

from rest_framework import serializers

class PerformanceDetailSerializer(serializers.Serializer):
    