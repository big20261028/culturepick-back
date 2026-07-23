from .base import *  # noqa: F401, F403

# ── 보안 강화 ─────────────────────────────────────────────────────────
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=False)  # noqa: F405
SESSION_COOKIE_SECURE = env.bool("DJANGO_SESSION_COOKIE_SECURE", default=False)  # noqa: F405
CSRF_COOKIE_SECURE = env.bool("DJANGO_CSRF_COOKIE_SECURE", default=False)  # noqa: F405
SECURE_HSTS_SECONDS = env.int("DJANGO_SECURE_HSTS_SECONDS", default=0)  # noqa: F405
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", default=False)  # noqa: F405

# ── CORS / CSRF: 운영 도메인만 허용 ───────────────────────────────────
CORS_ALLOWED_ORIGINS = env.list("CORS_ALLOWED_ORIGINS", default=[])  # noqa: F405
CSRF_TRUSTED_ORIGINS = env.list("CSRF_TRUSTED_ORIGINS", default=[])  # noqa: F405

# DRF throttles must use a cache shared by all Gunicorn workers and EB
# instances. Keep a separate key namespace even when Celery uses the same
# Redis/Valkey database.
CACHE_URL = env("CACHE_URL", default="") or REDIS_URL  # noqa: F405
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.redis.RedisCache",
        "LOCATION": CACHE_URL,
        "KEY_PREFIX": env("CACHE_KEY_PREFIX", default="culturepick-cache"),  # noqa: F405
        "TIMEOUT": 300,
    }
}

# One trusted proxy is correct for the current direct ALB -> EB request path.
# Change this value if CloudFront or another proxy layer is added.
REST_FRAMEWORK["NUM_PROXIES"] = env.int("DRF_NUM_PROXIES", default=1)  # noqa: F405

# ── 정적 파일: 컨테이너/EB에서 admin static 제공 ───────────────────────
MIDDLEWARE.insert(1, "whitenoise.middleware.WhiteNoiseMiddleware")  # noqa: F405
STATICFILES_STORAGE = "whitenoise.storage.CompressedManifestStaticFilesStorage"

# Media files: use S3 only when a bucket is configured. boto3 will use the
# Elastic Beanstalk EC2 role automatically when access keys are not provided.
AWS_STORAGE_BUCKET_NAME = env("AWS_STORAGE_BUCKET_NAME", default="")  # noqa: F405
AWS_S3_REGION_NAME = env("AWS_S3_REGION_NAME", default="ap-northeast-2")  # noqa: F405
AWS_S3_CUSTOM_DOMAIN = env("AWS_S3_CUSTOM_DOMAIN", default="")  # noqa: F405
AWS_ACCESS_KEY_ID = env("AWS_ACCESS_KEY_ID", default=None)  # noqa: F405
AWS_SECRET_ACCESS_KEY = env("AWS_SECRET_ACCESS_KEY", default=None)  # noqa: F405
AWS_DEFAULT_ACL = None
AWS_QUERYSTRING_AUTH = False
AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=86400"}

if AWS_S3_CUSTOM_DOMAIN:
    COMMUNITY_ALLOWED_IMAGE_HOSTS.add(AWS_S3_CUSTOM_DOMAIN.lower().rstrip("."))  # noqa: F405
elif AWS_STORAGE_BUCKET_NAME:
    COMMUNITY_ALLOWED_IMAGE_HOSTS.add(  # noqa: F405
        f"{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com".lower()
    )

STORAGES = {
    "staticfiles": {
        "BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage",
    },
}

if AWS_STORAGE_BUCKET_NAME:
    STORAGES["default"] = {
        "BACKEND": "storages.backends.s3boto3.S3Boto3Storage",
    }
    MEDIA_URL = (  # noqa: F405
        f"https://{AWS_S3_CUSTOM_DOMAIN}/"
        if AWS_S3_CUSTOM_DOMAIN
        else f"https://{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com/"
    )
else:
    STORAGES["default"] = {
        "BACKEND": "django.core.files.storage.FileSystemStorage",
    }

# ── 이메일 ────────────────────────────────────────────────────────────
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
EMAIL_HOST = env("EMAIL_HOST", default="")  # noqa: F405
EMAIL_PORT = env.int("EMAIL_PORT", default=587)  # noqa: F405
EMAIL_HOST_USER = env("EMAIL_HOST_USER", default="")  # noqa: F405
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD", default="")  # noqa: F405
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)  # noqa: F405
EMAIL_TIMEOUT = env.int("EMAIL_TIMEOUT", default=10)  # noqa: F405
