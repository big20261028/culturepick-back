'''
ModelSerializer: 모델과 연결된 데이터를 다룰 때
                 (조회, 생성, 수정 모두 포함)

Serializer:      모델과 무관한 일회성 데이터 검증
                 (로그인, 필터 검색어, 비밀번호 초기화 등)
'''

from rest_framework import serializers
from .models import (
    BookingLink,
    Performance,
    PerformanceImage,
    PerformancePrice,
    UsersPerformanceAction,
    Venue,
)

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


class PerformancePriceSerializer(serializers.ModelSerializer):
    class Meta:
        model = PerformancePrice
        fields = ('label', 'price', 'currency', 'raw_text', 'sort_order')


class BookingLinkSerializer(serializers.ModelSerializer):
    class Meta:
        model = BookingLink
        fields = ('site_name', 'url')


class PerformanceActionSerializer(serializers.Serializer):
    action_type = serializers.ChoiceField(choices=UsersPerformanceAction.ActionType.values)
    is_active = serializers.BooleanField(required=False, allow_null=True, default=None)


class PerformanceListSerializer(serializers.ModelSerializer):
    venue = VenueSerializer(read_only=True)
    price_options = PerformancePriceSerializer(many=True, read_only=True)
    search_score = serializers.IntegerField(read_only=True)
    is_interested = serializers.SerializerMethodField()
    is_watchlisted = serializers.SerializerMethodField()

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
            'price_options',
            'openrun',
            'is_child',
            'is_festival',
            'venue',
            'view_count',
            'zzim_count',
            'is_interested',
            'is_watchlisted',
            'search_score',
        )

    def _get_user_action_types(self, obj):
        if hasattr(obj, 'current_user_actions'):
            return {action.action_type for action in obj.current_user_actions}

        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return set()

        return set(
            obj.users_performance_actions.filter(user=request.user)
            .values_list('action_type', flat=True)
        )

    def get_is_interested(self, obj):
        return UsersPerformanceAction.ActionType.INTEREST in self._get_user_action_types(obj)

    def get_is_watchlisted(self, obj):
        return UsersPerformanceAction.ActionType.WATCHLIST in self._get_user_action_types(obj)


class PerformanceDetailSerializer(serializers.ModelSerializer):
    venue = VenueSerializer(read_only=True)
    images = PerformanceImageSerializer(many=True, read_only=True)
    price_options = PerformancePriceSerializer(many=True, read_only=True)
    booking_links = BookingLinkSerializer(many=True, read_only=True)

    is_interested = serializers.SerializerMethodField()
    is_watchlisted = serializers.SerializerMethodField()

    class Meta:
        model = Performance
        # fields = ()
        exclude = ('synced_at',)

    def _get_user_action_types(self, obj):
        if hasattr(obj, 'current_user_actions'):
            return {action.action_type for action in obj.current_user_actions}

        request = self.context.get('request')
        if not request or not request.user.is_authenticated:
            return set()

        return set(
            obj.users_performance_actions.filter(user=request.user)
            .values_list('action_type', flat=True)
        )

    def get_is_interested(self, obj):
        return UsersPerformanceAction.ActionType.INTEREST in self._get_user_action_types(obj)
    
    def get_is_watchlisted(self, obj):
        return UsersPerformanceAction.ActionType.WATCHLIST in self._get_user_action_types(obj)
