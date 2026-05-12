import os

from celery import Celery

# 환경에 따라 settings 모듈 선택
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "BE.settings.local")

app = Celery("culturepick")

# Django settings 에서 CELERY_ 접두사 설정 자동 로드
app.config_from_object("django.conf:settings", namespace="CELERY")

# 각 앱의 tasks.py 자동 탐색
app.autodiscover_tasks()


@app.task(bind=True, ignore_result=True)
def debug_task(self):
    print(f"Request: {self.request!r}")
