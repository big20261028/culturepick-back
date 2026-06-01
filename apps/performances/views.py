from django.db import transaction
from django.db.models import Case, F, IntegerField, Q, Value, When
from django.shortcuts import get_object_or_404
from rest_framework.generics import ListAPIView, RetrieveAPIView
from rest_framework.pagination import PageNumberPagination, _positive_int
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from .models import Performance, UsersPerformanceAction
from .serializers import (
    PerformanceActionSerializer,
    PerformanceDetailSerializer,
    PerformanceListSerializer,
)


GENRE_FILTERS = {
    "musical": ["musical", "뮤지컬"],
    "play": ["play", "연극"],
    "classic": ["classic", "클래식", "서양음악"],
    "koreanMusic": ["koreanMusic", "korean_music", "국악", "한국음악"],
    "concert": ["concert", "콘서트", "대중음악"],
    "dancing": ["dancing", "dance", "무용", "대중무용", "서커스", "마술", "복합"],
}

REGION_FILTERS = {
    "seoul": ["서울"],
    "서울": ["서울"],
    "gyeonggi": ["경기", "인천"],
    "경기/인천": ["경기", "인천"],
    "chungcheong": ["충청", "충북", "충남", "강원", "대전", "세종"],
    "충청/강원": ["충청", "충북", "충남", "강원", "대전", "세종"],
    "daegu": ["대구", "경북"],
    "대구/경북": ["대구", "경북"],
    "busan": ["부산", "경남", "울산"],
    "부산/경남": ["부산", "경남", "울산"],
    "gwangju": ["광주", "전라", "전북", "전남"],
    "광주/전라": ["광주", "전라", "전북", "전남"],
    "jeju": ["제주", "기타", "미분류", "해외"],
    "제주/기타": ["제주", "기타", "미분류", "해외"],
}

STATUS_FILTERS = {
    "upcomming": ["upcomming", "upcoming", "공연예정"],
    "upcoming": ["upcomming", "upcoming", "공연예정"],
    "performing": ["performing", "공연중"],
    "done": ["done", "공연완료"],
}


class PerformanceSearchPagination(PageNumberPagination):
    page_size = 20
    max_page_size = 100
    page_query_param = "pageNum"
    page_size_query_param = "pageSize"

    def get_page_number(self, request, paginator):
        return request.query_params.get("pageNum") or request.query_params.get("page") or 1

    def get_page_size(self, request):
        if self.page_size_query_param:
            page_size = request.query_params.get("pageSize") or request.query_params.get("page_size")
            if page_size:
                try:
                    return _positive_int(page_size, strict=True, cutoff=self.max_page_size)
                except (KeyError, ValueError):
                    pass
        return self.page_size

    def get_paginated_response(self, data):
        page_size = self.get_page_size(self.request)
        return Response({
            "pageNum": self.page.number,
            "pageSize": page_size,
            "total": self.page.paginator.count,
            "searchData": data,
            "page": self.page.number,
            "page_size": page_size,
            "results": data,
        })


class PerformanceListView(ListAPIView):
    permission_classes = [AllowAny]
    serializer_class = PerformanceListSerializer
    pagination_class = PerformanceSearchPagination

    def get_queryset(self):
        queryset = Performance.objects.select_related("venue")
        keyword = self.request.query_params.get("keyword", "").strip()
        has_feature_filters = any(
            self._get_query_param(name) for name in ("genre", "local", "region", "status")
        )

        queryset = self._apply_feature_filters(queryset)

        if keyword and has_feature_filters:
            queryset = queryset.filter(
                Q(title__icontains=keyword) | Q(venue__name__icontains=keyword)
            ).annotate(search_score=Value(0, output_field=IntegerField()))
        elif keyword:
            title_score = Case(
                When(title__icontains=keyword, then=Value(100)),
                default=Value(0),
                output_field=IntegerField(),
            )
            cast_score = Case(
                When(cast__icontains=keyword, then=Value(60)),
                default=Value(0),
                output_field=IntegerField(),
            )
            venue_score = Case(
                When(venue__name__icontains=keyword, then=Value(40)),
                default=Value(0),
                output_field=IntegerField(),
            )
            queryset = (
                queryset.filter(
                    Q(title__icontains=keyword)
                    | Q(cast__icontains=keyword)
                    | Q(venue__name__icontains=keyword)
                )
                .annotate(search_score=title_score + cast_score + venue_score)
            )
        else:
            queryset = queryset.annotate(search_score=Value(0, output_field=IntegerField()))

        return self._apply_sort(queryset, bool(keyword) and not has_feature_filters)

    def _get_query_param(self, name, default=""):
        return self.request.query_params.get(name, default).strip()

    def _split_param(self, value):
        return [item.strip() for item in value.split(",") if item.strip()]

    def _apply_feature_filters(self, queryset):
        genre = self._get_query_param("genre")
        local = self._get_query_param("local") or self._get_query_param("region")
        status = self._get_query_param("status")

        queryset = self._apply_genre_filter(queryset, genre)
        queryset = self._apply_region_filter(queryset, local)
        queryset = self._apply_status_filter(queryset, status)
        return queryset

    def _apply_genre_filter(self, queryset, genre):
        if not genre or genre in {"all", "전체"}:
            return queryset

        query = Q()
        for item in self._split_param(genre):
            values = GENRE_FILTERS.get(item, [item])
            for value in values:
                query |= Q(genre__icontains=value)
        return queryset.filter(query)

    def _apply_region_filter(self, queryset, local):
        if not local or local in {"all", "전체"}:
            return queryset

        query = Q()
        for item in self._split_param(local):
            values = REGION_FILTERS.get(item, [item])
            for value in values:
                query |= (
                    Q(venue__sido__icontains=value)
                    | Q(venue__gugun__icontains=value)
                    | Q(venue__address__icontains=value)
                )
        return queryset.filter(query)

    def _apply_status_filter(self, queryset, performance_status):
        if not performance_status or performance_status in {"all", "전체"}:
            return queryset

        query = Q()
        for item in self._split_param(performance_status):
            values = STATUS_FILTERS.get(item, [item])
            for value in values:
                query |= Q(status__iexact=value)
        return queryset.filter(query)

    def _apply_sort(self, queryset, has_keyword):
        sorted_by = self._get_query_param("sorted") or self._get_query_param("sort")

        if sorted_by in {"latest", "recent"}:
            return queryset.order_by(F("start_date").desc(nulls_last=True), "-synced_at", "title")
        if sorted_by in {"start_date", "date"}:
            return queryset.order_by("start_date", "title")
        if sorted_by == "title":
            return queryset.order_by("title", "performance_id")
        if sorted_by in {"popular", "views"}:
            return queryset.order_by("-view_count", "title")
        if sorted_by == "zzim":
            return queryset.order_by("-zzim_count", "title")
        if sorted_by == "rating":
            return queryset.order_by(F("start_date").desc(nulls_last=True), "-synced_at", "title")
        if has_keyword:
            return queryset.order_by("-search_score", "title", "performance_id")
        return queryset.order_by(
            F("start_date").desc(nulls_last=True),
            "-synced_at",
            "title",
            "performance_id",
        )


class PerformanceDetailView(RetrieveAPIView):
    permission_classes = [AllowAny]
    serializer_class = PerformanceDetailSerializer
    lookup_field = "performance_id"
    lookup_url_kwarg = "performance_id"

    queryset = (
        Performance.objects.select_related("venue")
        .prefetch_related("images", "booking_links")
    )

    def get_object(self):
        performance = super().get_object()
        Performance.objects.filter(pk=performance.pk).update(view_count=F("view_count") + 1)
        performance.view_count += 1
        return performance


class PerformanceActionView(APIView):
    permission_classes = [IsAuthenticated]

    def post(self, request, performance_id):
        performance = get_object_or_404(Performance, pk=performance_id)
        serializer = PerformanceActionSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        action_type = serializer.validated_data["action_type"]
        requested_state = serializer.validated_data.get("is_active")

        with transaction.atomic():
            action_queryset = UsersPerformanceAction.objects.filter(
                user=request.user,
                performance=performance,
                action_type=action_type,
            )
            exists = action_queryset.exists()
            is_active = not exists if requested_state is None else requested_state

            if is_active and not exists:
                UsersPerformanceAction.objects.create(
                    user=request.user,
                    performance=performance,
                    action_type=action_type,
                )
            elif not is_active and exists:
                action_queryset.delete()

            if action_type == UsersPerformanceAction.ActionType.INTEREST:
                zzim_count = UsersPerformanceAction.objects.filter(
                    performance=performance,
                    action_type=UsersPerformanceAction.ActionType.INTEREST,
                ).count()
                Performance.objects.filter(pk=performance.pk).update(zzim_count=zzim_count)
                performance.zzim_count = zzim_count

        is_interested = UsersPerformanceAction.objects.filter(
            user=request.user,
            performance=performance,
            action_type=UsersPerformanceAction.ActionType.INTEREST,
        ).exists()
        is_watchlisted = UsersPerformanceAction.objects.filter(
            user=request.user,
            performance=performance,
            action_type=UsersPerformanceAction.ActionType.WATCHLIST,
        ).exists()

        return Response({
            "performance_id": performance.performance_id,
            "action_type": action_type,
            "is_active": is_active,
            "is_interested": is_interested,
            "is_watchlisted": is_watchlisted,
            "zzim_count": performance.zzim_count,
        })
