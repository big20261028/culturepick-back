#!/bin/bash

SRC="files (1)-1"

echo "[1/5] kopis 파일 배치..."
cp "$SRC/client.py"   apps/performances/kopis/client.py
cp "$SRC/parser.py"   apps/performances/kopis/parser.py
cp "$SRC/sync.py"     apps/performances/kopis/sync.py

echo "[2/5] performances 파일 배치..."
cp "$SRC/models.py"   apps/performances/models.py
cp "$SRC/tasks.py"    apps/performances/tasks.py

echo "[3/5] management/commands 생성..."
mkdir -p apps/performances/management/commands
touch apps/performances/management/__init__.py
touch apps/performances/management/commands/__init__.py
cp "$SRC/sync_kopis.py" apps/performances/management/commands/sync_kopis.py

echo "[4/5] 빈 파일 생성..."

cat > apps/users/urls.py << 'EOF'
from django.urls import path
urlpatterns = []
EOF

cat > apps/performances/urls.py << 'EOF'
from django.urls import path
urlpatterns = []
EOF

cat > apps/logs/urls.py << 'EOF'
from django.urls import path
urlpatterns = []
EOF

cat > apps/logs/models.py << 'EOF'
from django.db import models
from django.conf import settings


class SearchLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="search_logs"
    )
    keyword = models.CharField(max_length=255, blank=True)
    filter_region = models.CharField(max_length=100, blank=True)
    filter_genre = models.CharField(max_length=100, blank=True)
    filter_status = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "search_logs"


class ViewLog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="view_logs"
    )
    performance_id = models.CharField(max_length=20)
    log_type = models.CharField(max_length=50, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "view_logs"


class QnALog(models.Model):
    user = models.ForeignKey(
        settings.AUTH_USER_MODEL, on_delete=models.SET_NULL,
        null=True, blank=True, related_name="qna_logs"
    )
    question = models.TextField()
    answer = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = "qna_logs"
EOF

cat > common/permissions.py << 'EOF'
from rest_framework.permissions import BasePermission


class IsAdminUser(BasePermission):
    def has_permission(self, request, view):
        return bool(request.user and request.user.is_authenticated and request.user.is_admin)
EOF

echo "[5/5] apps.py name 수정..."

cat > apps/users/apps.py << 'EOF'
from django.apps import AppConfig

class UsersConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.users"
EOF

cat > apps/performances/apps.py << 'EOF'
from django.apps import AppConfig

class PerformancesConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.performances"
EOF

cat > apps/logs/apps.py << 'EOF'
from django.apps import AppConfig

class LogsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.logs"
EOF

echo ""
echo "완료! 확인 중..."
python manage.py check
