"""
공통 Django 설정 (base.py)
local.py / production.py 가 이 파일을 상속합니다.
"""

from pathlib import Path

import environ

# ── 경로 설정 ─────────────────────────────────────────────────────────
# BASE_DIR = culturepick-be/
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# ── 환경 변수 로드 ────────────────────────────────────────────────────
env = environ.Env()
environ.Env.read_env(BASE_DIR / ".env")

# ── 보안 ──────────────────────────────────────────────────────────────
SECRET_KEY = env("DJANGO_SECRET_KEY")
DEBUG = env.bool("DJANGO_DEBUG", default=False)
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=[])

# ── 앱 등록 ───────────────────────────────────────────────────────────
DJANGO_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
]

THIRD_PARTY_APPS = [
    "rest_framework",
    "rest_framework_simplejwt",
    "rest_framework_simplejwt.token_blacklist",
    "corsheaders",
    "social_django",
    "django_celery_beat",
    "django_celery_results",
]

LOCAL_APPS = [
    "apps.users",
    "apps.performances",
    "apps.logs",
    "apps.recommendations",
    "apps.community",
]

INSTALLED_APPS = DJANGO_APPS + THIRD_PARTY_APPS + LOCAL_APPS

# ── 미들웨어 ──────────────────────────────────────────────────────────
MIDDLEWARE = [
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",        # CORS: 최상단 근처 필수
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

# ── URL / WSGI ────────────────────────────────────────────────────────
ROOT_URLCONF = "BE.urls"
WSGI_APPLICATION = "BE.wsgi.application"

# ── 템플릿 ────────────────────────────────────────────────────────────
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
                "social_django.context_processors.backends",
            ],
        },
    },
]

# ── 데이터베이스 ──────────────────────────────────────────────────────
database_url = env("DATABASE_URL", default="")
if database_url:
    default_database = env.db("DATABASE_URL")
elif env("DB_HOST", default=""):
    default_database = {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": env("DB_NAME", default="culturepick"),
        "USER": env("DB_USER", default="postgres"),
        "PASSWORD": env("DB_PASSWORD", default=""),
        "HOST": env("DB_HOST"),
        "PORT": env("DB_PORT", default="5432"),
    }
else:
    default_database = env.db(
        "DATABASE_URL",
        default="postgresql://postgres:postgres@localhost:5432/culturepick",
    )

DATABASES = {"default": default_database}
DATABASES["default"]["ATOMIC_REQUESTS"] = True  # 요청 단위 트랜잭션

# ── 커스텀 유저 모델 ──────────────────────────────────────────────────
AUTH_USER_MODEL = "users.User"

# ── 비밀번호 검증 ─────────────────────────────────────────────────────
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# ── 국제화 ────────────────────────────────────────────────────────────
LANGUAGE_CODE = "ko-kr"
TIME_ZONE = "Asia/Seoul"
USE_I18N = True
USE_TZ = True

# ── 정적 파일 ─────────────────────────────────────────────────────────
STATIC_URL = "/static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── DRF 설정 ──────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework_simplejwt.authentication.JWTAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": (
        "rest_framework.permissions.IsAuthenticated",
    ),
    "DEFAULT_PAGINATION_CLASS": "common.pagination.StandardResultsPagination",
    "PAGE_SIZE": 20,
    "DEFAULT_RENDERER_CLASSES": (
        "rest_framework.renderers.JSONRenderer",
    ),
    "EXCEPTION_HANDLER": "common.exceptions.custom_exception_handler",
}

# ── JWT 설정 ──────────────────────────────────────────────────────────
from datetime import timedelta

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(hours=1),
    "REFRESH_TOKEN_LIFETIME": timedelta(days=14),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": True,
    "AUTH_HEADER_TYPES": ("Bearer",),
}

# ── 소셜 로그인 ───────────────────────────────────────────────────────
AUTHENTICATION_BACKENDS = (
    "social_core.backends.google.GoogleOAuth2",
    "social_core.backends.kakao.KakaoOAuth2",
    "social_core.backends.naver.NaverOAuth2",
    "django.contrib.auth.backends.ModelBackend",
)
SOCIAL_AUTH_GOOGLE_OAUTH2_KEY = env("GOOGLE_CLIENT_ID", default="")
SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET = env("GOOGLE_CLIENT_SECRET", default="")
SOCIAL_AUTH_KAKAO_KEY = env("KAKAO_CLIENT_ID", default="")
SOCIAL_AUTH_NAVER_KEY = env("NAVER_CLIENT_ID", default="")
SOCIAL_AUTH_NAVER_SECRET = env("NAVER_CLIENT_SECRET", default="")

# ── Celery ────────────────────────────────────────────────────────────
CELERY_BROKER_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_RESULT_BACKEND = "django-db"          # django_celery_results
CELERY_RESULT_EXTENDED = True
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"

from celery.schedules import crontab

CELERY_BEAT_SCHEDULE = {
    "sync-ongoing-performances": {
        "task": "apps.performances.tasks.sync_ongoing_performances",
        "schedule": crontab(hour=4, minute=0),
    },
    "sync-upcoming-performances": {
        "task": "apps.performances.tasks.sync_upcoming_performances",
        "schedule": crontab(hour=4, minute=30),
    },
}

# ── KOPIS API ─────────────────────────────────────────────────────────
KOPIS_API_KEY = env("KOPIS_API_KEY", default="")

# OpenAI recommendation API
OPENAI_API_SECRET_KEY = env("OPENAI_API_SECRET_KEY", default=env("OPENAI_API_KEY", default=""))
OPENAI_RECOMMENDATION_MODEL = env("OPENAI_RECOMMENDATION_MODEL", default="gpt-4o-mini")

# ── 로깅 ──────────────────────────────────────────────────────────────
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "[{asctime}] {levelname} {name} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "verbose",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "apps": {"handlers": ["console"], "level": "DEBUG", "propagate": False},
        "django.db.backends": {"handlers": ["console"], "level": "WARNING"},
    },
}

import mimetypes

mimetypes.add_type('application/javascript','.js', True)
