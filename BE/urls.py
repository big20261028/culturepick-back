from django.conf import settings
from django.contrib import admin
from django.urls import include, path

urlpatterns = [
    path("admin/", admin.site.urls),

    # API v1
    path("api/v1/auth/", include("apps.users.urls")),
    path("api/v1/performances/", include("apps.performances.urls")),
    path("api/v1/logs/", include("apps.logs.urls")),

    # 소셜 로그인
    path("social/", include("social_django.urls", namespace="social")),
]

# 로컬 개발에서만 debug_toolbar 활성화
if settings.DEBUG:
    import debug_toolbar
    urlpatterns += [path("__debug__/", include(debug_toolbar.urls))]
