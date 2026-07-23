"""
공통 Django 설정 (base.py)
local.py / production.py 가 이 파일을 상속합니다.
"""

import mimetypes
import ssl
from datetime import timedelta
from pathlib import Path

import environ
from celery.schedules import crontab

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
COMMUNITY_ALLOWED_IMAGE_HOSTS = {
    host.strip().lower().rstrip(".")
    for host in env.list("COMMUNITY_ALLOWED_IMAGE_HOSTS", default=[])
    if host.strip()
}

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# ── DRF 설정 ──────────────────────────────────────────────────────────
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "apps.users.authentication.AuthVersionJWTAuthentication",
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
    # Local requests do not pass through a trusted reverse proxy. Production
    # overrides this with the verified EB/ALB proxy count.
    "NUM_PROXIES": 0,
    "DEFAULT_THROTTLE_RATES": {
        "password_reset_request": env("PASSWORD_RESET_REQUEST_THROTTLE_RATE", default="5/hour"),
        "password_reset_confirm": env("PASSWORD_RESET_CONFIRM_THROTTLE_RATE", default="10/hour"),
        "account_recovery": env("ACCOUNT_RECOVERY_THROTTLE_RATE", default="5/hour"),
    },
}

# ── 계정 복구 이메일 ─────────────────────────────────────────────────
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL", default="noreply@culturepick.net")
FRONTEND_PASSWORD_RESET_URL = env(
    "FRONTEND_PASSWORD_RESET_URL",
    default="https://culturepick.netlify.app/find-account",
)
FRONTEND_LOGIN_URL = env(
    "FRONTEND_LOGIN_URL",
    default="https://culturepick.netlify.app/login",
)
PASSWORD_RESET_TIMEOUT = env.int("PASSWORD_RESET_TIMEOUT", default=3600)

# ── JWT 설정 ──────────────────────────────────────────────────────────
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
REDIS_URL = env("REDIS_URL", default="redis://localhost:6379/0")
CELERY_BROKER_URL = env("CELERY_BROKER_URL", default="") or REDIS_URL
CELERY_RESULT_BACKEND = env("CELERY_RESULT_BACKEND", default="") or "django-db"
CELERY_RESULT_EXTENDED = True
CELERY_TIMEZONE = TIME_ZONE
CELERY_TASK_SERIALIZER = "json"
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_BROKER_CONNECTION_RETRY_ON_STARTUP = True
CELERY_WORKER_ENABLE_REMOTE_CONTROL = env.bool("CELERY_WORKER_ENABLE_REMOTE_CONTROL", default=False)

CELERY_REDIS_GLOBAL_KEYPREFIX = env("CELERY_REDIS_GLOBAL_KEYPREFIX", default="{culturepick-celery}:")
CELERY_BROKER_TRANSPORT_OPTIONS = {
    "global_keyprefix": CELERY_REDIS_GLOBAL_KEYPREFIX,
}

CELERY_REDIS_RESULT_GLOBAL_KEYPREFIX = env(
    "CELERY_REDIS_RESULT_GLOBAL_KEYPREFIX",
    default="{culturepick-celery-result}:",
)
CELERY_RESULT_BACKEND_TRANSPORT_OPTIONS = {
    "global_keyprefix": CELERY_REDIS_RESULT_GLOBAL_KEYPREFIX,
}

LOG_RAW_RETENTION_DAYS = env.int("LOG_RAW_RETENTION_DAYS", default=90)
LOG_RETENTION_BATCH_SIZE = env.int("LOG_RETENTION_BATCH_SIZE", default=1000)

if CELERY_BROKER_URL.startswith("rediss://"):
    CELERY_BROKER_USE_SSL = {"ssl_cert_reqs": ssl.CERT_NONE}

if isinstance(CELERY_RESULT_BACKEND, str) and CELERY_RESULT_BACKEND.startswith("rediss://"):
    CELERY_REDIS_BACKEND_USE_SSL = {"ssl_cert_reqs": ssl.CERT_NONE}

CELERY_ENABLE_KOPIS_BEAT_SCHEDULE = env.bool("CELERY_ENABLE_KOPIS_BEAT_SCHEDULE", default=False)
KOPIS_ONGOING_SYNC_DAYS = env.int("KOPIS_ONGOING_SYNC_DAYS", default=30)
KOPIS_UPCOMING_SYNC_DAYS = env.int("KOPIS_UPCOMING_SYNC_DAYS", default=60)
KOPIS_SYNC_LOCK_TTL_SECONDS = env.int("KOPIS_SYNC_LOCK_TTL_SECONDS", default=7200)
CELERY_BEAT_SCHEDULE = {}

if CELERY_ENABLE_KOPIS_BEAT_SCHEDULE:
    CELERY_BEAT_SCHEDULE = {
        "sync-ongoing-performances": {
            "task": "apps.performances.tasks.sync_ongoing_performances",
            "schedule": crontab(hour=4, minute=10),
        },
        "sync-upcoming-performances": {
            "task": "apps.performances.tasks.sync_upcoming_performances",
            "schedule": crontab(hour=4, minute=30),
        },
    }

# ── KOPIS API ─────────────────────────────────────────────────────────
KOPIS_API_KEY = env("KOPIS_API_KEY", default="")

# AI recommendation API
AI_RECOMMENDATION_PROVIDER = env("AI_RECOMMENDATION_PROVIDER", default="openai")
AI_RECOMMENDATION_MAX_OUTPUT_TOKENS = env.int("AI_RECOMMENDATION_MAX_OUTPUT_TOKENS", default=1200)
AI_RECOMMENDATION_TEMPERATURE = env.float("AI_RECOMMENDATION_TEMPERATURE", default=0.35)
AI_RECOMMENDATION_CANDIDATE_LIMIT_DEFAULT = env.int("AI_RECOMMENDATION_CANDIDATE_LIMIT_DEFAULT", default=12)
AI_RECOMMENDATION_DEMO_INTENT_ENABLED = env.bool("AI_RECOMMENDATION_DEMO_INTENT_ENABLED", default=True)
OPENAI_API_SECRET_KEY = env("OPENAI_API_SECRET_KEY", default=env("OPENAI_API_KEY", default=""))
OPENAI_RECOMMENDATION_MODEL = env("OPENAI_RECOMMENDATION_MODEL", default="gpt-4o-mini")
GMS_API_KEY = env("GMS_API_KEY", default=env("GMS_KEY", default=""))
GMS_OPENAI_BASE_URL = env("GMS_OPENAI_BASE_URL", default="https://gms.ssafy.io/gmsapi/api.openai.com/v1")
GMS_RECOMMENDATION_MODEL = env("GMS_RECOMMENDATION_MODEL", default="gpt-4.1")

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

mimetypes.add_type("application/javascript", ".js", True)
