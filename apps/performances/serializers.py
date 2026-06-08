'''
ModelSerializer: 모델과 연결된 데이터를 다룰 때
                 (조회, 생성, 수정 모두 포함)

Serializer:      모델과 무관한 일회성 데이터 검증
                 (로그인, 필터 검색어, 비밀번호 초기화 등)
'''

from rest_framework import serializers
from .models import Performance, Venue, PerformanceImage, BookingLink, UsersPerformanceAction

class VenueSerializer(serializers.ModelSerializer):
    class Meta:
        model = Venue
        fields = (
            'venue_id',
            'name',
            'sido',
            'gugun',
            'address',
            'latitude',
            'longitude',
        )


class PerformanceImageSerializer(serializers.ModelSerializer):
    class Meta:
        model = PerformanceImage
        fields = ('image_url', 'sort_order')


class BookingLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookingLink
        fields = ('site_name', 'url')


class PerformanceActionSerializer(serializers.Serializer):
    action_type = serializers.ChoiceField(choices=UsersPerformanceAction.ActionType.values)
    is_active = serializers.BooleanField(required=False, allow_null=True, default=None)


class PerformanceListSerializer(serializers.ModelSerializer):
    venue = VenueSerializer(read_only=True)
    search_score = serializers.IntegerField(read_only=True)

    class Meta:
        model = Performance
        fields = (
            'performance_id',
            'title',
            'genre',
            'genre_code',
            'start_date',
            'end_date',
            'status',
            'status_code',
            'poster_url',
            'runtime',
            'age_rating',
            'min_price',
            'max_price',
            'is_free',
            'openrun',
            'is_child',
            'is_festival',
            'venue',
            'view_count',
            'zzim_count',
            'search_score',
        )


class PerformanceDetailSerializer(serializers.ModelSerializer):
    venue = VenueSerializer(read_only=True)
    images = PerformanceImageSerializer(many=True, read_only=True)
    booking_links = BookingLinkSerializer(many=True, read_only=True)

    is_interested = serializers.SerializerMethodField()
    is_watchlisted = serializers.SerializerMethodField()

    class Meta:
        model = Performance
        # fields = ()
        exclude = ('synced_at',)

    def get_is_interested(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.users_performance_actions.filter(
            user=request.user,
            action_type='interest'
        ).exists()
    
    def get_is_watchlisted(self, obj):
        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return False
        return obj.users_performance_actions.filter(
            user=request.user,
            action_type='watchlist'
        ).exists()
