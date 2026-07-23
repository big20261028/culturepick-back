import ssl

from django.conf import settings
from django.db import connections
from django.http import JsonResponse
from redis import Redis
from redis.exceptions import RedisError


def health_check(request):
    return JsonResponse({"status": "ok"})


def _check_database():
    connection = connections["default"]
    connection.ensure_connection()
    with connection.cursor() as cursor:
        cursor.execute("SELECT 1")


def _check_redis():
    redis_url = settings.REDIS_URL
    options = {
        "socket_connect_timeout": 1,
        "socket_timeout": 1,
    }
    if redis_url.startswith("rediss://"):
        options["ssl_cert_reqs"] = ssl.CERT_NONE

    client = Redis.from_url(redis_url, **options)
    try:
        client.ping()
    finally:
        client.close()


def readiness_check(request):
    checks = {}

    try:
        _check_database()
        checks["database"] = "ok"
    except Exception:
        checks["database"] = "unavailable"

    try:
        _check_redis()
        checks["redis"] = "ok"
    except (RedisError, OSError, ValueError):
        checks["redis"] = "unavailable"

    is_ready = all(value == "ok" for value in checks.values())
    return JsonResponse(
        {"status": "ok" if is_ready else "unavailable", "checks": checks},
        status=200 if is_ready else 503,
    )
