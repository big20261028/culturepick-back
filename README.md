# CulturePick Backend

CulturePick은 공연 검색, 사용자 행동 로그 기반 추천, AI 추천 챗봇, 커뮤니티, 마이페이지를 제공하는 공연 추천 서비스입니다.

이 저장소는 CulturePick의 Django REST API 백엔드입니다. KOPIS 공연 데이터를 수집해 PostgreSQL에 저장하고, 사용자의 관심/볼예정/조회/검색 로그를 기반으로 추천 후보를 계산한 뒤 OpenAI 호환 API 또는 SSAFY GMS를 통해 추천 이유를 생성합니다.

API 사용법은 [API.md](./API.md)를 확인하세요.

## 주요 기능

### 공연 데이터

- KOPIS 공연/공연장 데이터 수집
- 공연 목록/상세 조회
- 장르, 지역, 상태, 키워드 검색
- 관심 공연, 볼 예정 공연 등록/해제
- 좌석별 가격 정보 분리 저장
- 공연장 주소 기반 `sido`, `gugun` 자동 보정

### 사용자/인증

- 이메일 회원가입/로그인/로그아웃
- JWT access/refresh token
- Google, Kakao, Naver 소셜 로그인
- 마이페이지 프로필 조회/수정
- 비밀번호 재확인 후 회원정보 수정
- 관심 공연, 볼 예정 공연, 내가 쓴 글 조회

### 추천/AI

- 사용자 로그 기반 추천 후보 계산
- 요청 문장 기반 intent 반영
- OpenAI 또는 SSAFY GMS 기반 추천 이유 생성
- 추천 피드백 저장
- 파인튜닝 학습 후보 자동 분류
- 시연 안정화를 위한 demo intent 모듈 제공

### 커뮤니티

- 자유게시판 게시글 CRUD
- 댓글 CRUD
- 게시글 카테고리/검색
- Tiptap/Toast 에디터 이미지 업로드
- S3 이미지 저장

### 운영

- AWS Elastic Beanstalk Docker 배포
- RDS PostgreSQL
- ElastiCache Valkey Redis
- Celery worker/beat
- S3 media storage
- `/health/` 헬스 체크
- 배포 후 migrate hook

## 기술 스택

- Python 3.12
- Django 5.1
- Django REST Framework
- Simple JWT
- PostgreSQL
- Redis / Valkey
- Celery
- django-celery-beat
- django-celery-results
- django-storages
- boto3
- OpenAI Python SDK
- Gunicorn
- Docker / Docker Compose
- AWS Elastic Beanstalk, RDS, ElastiCache, S3

## 프로젝트 구조

```text
culturepick-back/
├── BE/
│   ├── urls.py
│   ├── celery.py
│   └── settings/
│       ├── base.py
│       ├── local.py
│       └── production.py
├── apps/
│   ├── users/
│   ├── performances/
│   ├── logs/
│   ├── recommendations/
│   └── community/
├── common/
├── docker/
├── requirements/
├── .platform/hooks/postdeploy/
├── docker-compose.local.yml
├── docker-compose.yml
├── Dockerfile
├── manage.py
├── API.md
└── README.md
```

## 로컬 실행

### 1. 가상환경 활성화

Git Bash:

```bash
source .venv/Scripts/activate
```

PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

가상환경 확인:

```bash
python -c "import sys; print(sys.executable)"
python -m pip -V
```

`sys.executable`과 `pip -V`가 프로젝트의 `.venv`를 가리키면 정상입니다.

### 2. 의존성 설치

```bash
python -m pip install -r requirements/local.txt
```

### 3. 환경 변수 준비

```bash
cp .env.example .env
```

Windows PowerShell에서는 직접 `.env.example`을 복사해 `.env`를 만들어도 됩니다.

### 4. 로컬 DB/Redis 실행

```bash
docker compose -f docker-compose.local.yml up -d
```

### 5. 마이그레이션 및 서버 실행

```bash
python manage.py migrate
python manage.py runserver
```

헬스 체크:

```http
GET http://127.0.0.1:8000/health/
```

정상 응답:

```json
{"status": "ok"}
```

## 환경 변수

실제 `.env`, DB 비밀번호, API Key는 Git에 올리지 않습니다.

### Django

```env
DJANGO_SETTINGS_MODULE=BE.settings.production
DJANGO_SECRET_KEY=change-me
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=culturepick.ap-northeast-2.elasticbeanstalk.com
DJANGO_SECURE_SSL_REDIRECT=False
DJANGO_SESSION_COOKIE_SECURE=False
DJANGO_CSRF_COOKIE_SECURE=False
DJANGO_SECURE_HSTS_SECONDS=0
```

### Database

```env
DATABASE_URL=postgresql://USER:PASSWORD@RDS_ENDPOINT:5432/culturepick
```

또는:

```env
DB_NAME=culturepick
DB_USER=your-rds-user
DB_PASSWORD=your-rds-password
DB_HOST=your-rds-endpoint
DB_PORT=5432
```

### KOPIS

```env
KOPIS_API_KEY=your-kopis-api-key
KOPIS_ONGOING_SYNC_DAYS=30
KOPIS_UPCOMING_SYNC_DAYS=60
KOPIS_SYNC_LOCK_TTL_SECONDS=7200
```

### Redis/Celery

```env
REDIS_URL=rediss://your-valkey-endpoint:6379/0
CELERY_BROKER_URL=rediss://your-valkey-endpoint:6379/0
CELERY_RESULT_BACKEND=django-db
CELERY_ENABLE_KOPIS_BEAT_SCHEDULE=False
CELERY_WORKER_ENABLE_REMOTE_CONTROL=False
CELERY_REDIS_GLOBAL_KEYPREFIX={culturepick-celery}:
CELERY_REDIS_RESULT_GLOBAL_KEYPREFIX={culturepick-celery-result}:
```

### AI 추천

OpenAI:

```env
AI_RECOMMENDATION_PROVIDER=openai
OPENAI_API_SECRET_KEY=your-openai-key
OPENAI_RECOMMENDATION_MODEL=gpt-4o-mini
```

SSAFY GMS:

```env
AI_RECOMMENDATION_PROVIDER=gms
GMS_API_KEY=your-gms-key
GMS_OPENAI_BASE_URL=https://gms.ssafy.io/gmsapi/api.openai.com/v1
GMS_RECOMMENDATION_MODEL=gpt-4.1
```

시연/비용 제어:

```env
AI_RECOMMENDATION_MAX_OUTPUT_TOKENS=500
AI_RECOMMENDATION_TEMPERATURE=0.35
AI_RECOMMENDATION_CANDIDATE_LIMIT_DEFAULT=8
AI_RECOMMENDATION_DEMO_INTENT_ENABLED=True
```

`AI_RECOMMENDATION_MAX_OUTPUT_TOKENS`는 출력 토큰 상한입니다. 한 요청의 전체 사용량을 줄이려면 `AI_RECOMMENDATION_CANDIDATE_LIMIT_DEFAULT`도 함께 낮춥니다.

시연 후 demo intent를 끄려면:

```env
AI_RECOMMENDATION_DEMO_INTENT_ENABLED=False
```

### S3

```env
AWS_STORAGE_BUCKET_NAME=your-bucket-name
AWS_S3_REGION_NAME=ap-northeast-2
AWS_S3_CUSTOM_DOMAIN=your-bucket-name.s3.ap-northeast-2.amazonaws.com
AWS_ACCESS_KEY_ID=
AWS_SECRET_ACCESS_KEY=
```

운영에서는 access key를 직접 넣기보다 Elastic Beanstalk EC2 IAM Role 권한 사용을 권장합니다.

### CORS/CSRF

```env
CORS_ALLOWED_ORIGINS=https://culturepick.netlify.app
CSRF_TRUSTED_ORIGINS=https://culturepick.netlify.app
```

Netlify 주소 끝에는 `/`를 붙이지 않습니다.

## 프론트 연동 요약

자세한 API 요청/응답은 [API.md](./API.md)에 정리되어 있습니다.

프론트에서 특히 주의할 점:

- API base URL은 운영 EB 도메인 사용
- 인증 API 응답의 access token을 `Authorization: Bearer <access_token>`으로 전달
- access token 만료 시 `/api/v1/auth/token/refresh/` 호출
- 게시판 카테고리 요청값은 영어 저장값 사용
- 에디터 이미지는 `/api/v1/community/images/`에 multipart 업로드 후 `url` 또는 `image_url`을 본문에 삽입
- 공연 상세/관심/볼예정 API는 `performance_id` 사용
- 관심/볼예정 버튼은 `is_interested`, `is_watchlisted` 응답값으로 UI 갱신
- 추천 API는 로그인 필요
- 추천 피드백 저장 시 `session_id` 보관
- CORS origin에는 trailing slash를 넣지 않음
- 게시판 본문 HTML 렌더링 시 DOMPurify 등 sanitizer 사용 권장

## KOPIS 데이터 적재

### 전체 기본 적재

```bash
python manage.py sync_kopis --with-venues
```

### 기간 지정

```bash
python manage.py sync_kopis --stdate 20260601 --eddate 20261231 --with-venues
```

### 장르별 적재

```bash
python manage.py sync_kopis --stdate 20260601 --eddate 20261231 --genre CCCC --with-venues
```

주요 KOPIS 장르 코드:

| 코드 | 장르 |
|---|---|
| `AAAA` | 연극 |
| `GGGA` | 뮤지컬 |
| `CCCA` | 서양음악/클래식 |
| `CCCC` | 한국음악/국악 |
| `CCCD` | 대중음악 |
| `BBBC` | 무용 |

공연장만 갱신:

```bash
python manage.py sync_kopis --venues-only
```

기존 공연장 지역 보정:

```bash
python manage.py fill_venue_region
python manage.py fill_venue_region --overwrite
```

가격 테이블 재생성:

```bash
python manage.py rebuild_performance_prices
```

## Redis/Celery 운영

AWS 배포용 compose는 다음 3개 컨테이너를 실행합니다.

```text
web
celery-worker
celery-beat
```

컨테이너 확인:

```bash
sudo docker ps -a --format "table {{.Names}}\t{{.Status}}\t{{.Image}}\t{{.Command}}"
```

Redis 연결 확인:

```bash
sudo docker exec -it current-web-1 python manage.py shell -c "import os, ssl, redis; r=redis.from_url(os.environ['REDIS_URL'], ssl_cert_reqs=ssl.CERT_NONE); print(r.ping())"
```

Celery 로그:

```bash
sudo docker logs --tail=200 current-celery-worker-1
sudo docker logs --tail=200 current-celery-beat-1
```

KOPIS 주기 수집 스케줄 등록:

```bash
sudo docker exec -it current-web-1 python manage.py setup_celery_beat_schedule
```

등록되는 작업:

```text
daily-sync-ongoing-performances  -> 매일 04:10 Asia/Seoul
daily-sync-upcoming-performances -> 매일 04:30 Asia/Seoul
```

등록 확인:

```bash
sudo docker exec -it current-web-1 python manage.py shell -c "from django_celery_beat.models import PeriodicTask; print(list(PeriodicTask.objects.filter(name__in=['daily-sync-ongoing-performances','daily-sync-upcoming-performances','celery.backend_cleanup']).values('name','task','enabled','crontab__hour','crontab__minute','crontab__timezone')))"
```

## AWS 배포

### 배포 구조

```text
Elastic Beanstalk Docker
├── web            -> gunicorn BE.wsgi:application --bind 0.0.0.0:8000 --workers 1
├── celery-worker  -> celery -A BE worker -l info --concurrency=1 --without-mingle --without-gossip
└── celery-beat    -> celery -A BE beat -l info --scheduler django_celery_beat.schedulers:DatabaseScheduler

RDS PostgreSQL
ElastiCache Valkey
S3
```

### 배포 zip 주의사항

zip 최상단에 다음 파일/폴더가 바로 보여야 합니다.

```text
Dockerfile
docker-compose.yml
manage.py
BE/
apps/
common/
requirements/
docker/
```

제외 대상:

```text
.git/
.venv/
venv/
env/
.env
*.zip
*.sqlite3
staticfiles/
media/
deploy/
sync_log.txt
*.pdf
```

`.ebignore`에 기본 제외 규칙이 들어 있습니다.

### 배포 후 확인

헬스 체크:

```bash
curl -i http://culturepick.ap-northeast-2.elasticbeanstalk.com/health/
```

정상:

```json
{"status": "ok"}
```

컨테이너 확인:

```bash
sudo docker ps -a
```

명령 확인:

```bash
sudo docker inspect current-web-1 --format='Cmd={{json .Config.Cmd}}'
sudo docker inspect current-celery-worker-1 --format='Cmd={{json .Config.Cmd}}'
```

메모리 확인:

```bash
free -h
```

micro급 인스턴스에서는 다음 설정을 유지합니다.

```text
gunicorn workers=1
celery concurrency=1
```

수동 migrate:

```bash
sudo docker exec -it current-web-1 python manage.py migrate
```

관리자 계정 생성:

```bash
sudo docker exec -it current-web-1 python manage.py createsuperuser
```

## 검증 명령

로컬에서 RDS 대신 SQLite로 테스트하려면 임시 `DATABASE_URL`을 지정합니다.

PowerShell:

```powershell
$env:DATABASE_URL='sqlite:///test_local.sqlite3'
.\.venv\Scripts\python.exe manage.py check
.\.venv\Scripts\python.exe manage.py test apps.users apps.logs apps.performances apps.recommendations apps.community
Remove-Item Env:DATABASE_URL
Remove-Item test_local.sqlite3 -Force
```

Git Bash:

```bash
DATABASE_URL=sqlite:///test_local.sqlite3 python manage.py check
DATABASE_URL=sqlite:///test_local.sqlite3 python manage.py test apps.users apps.logs apps.performances apps.recommendations apps.community
rm -f test_local.sqlite3
```

개별 테스트:

```bash
python manage.py test apps.users.tests
python manage.py test apps.performances.tests
python manage.py test apps.recommendations.tests
python manage.py test apps.community.tests
```

## 발표 시연 추천 순서

1. `/health/`로 서버 상태 확인
2. 회원가입/로그인
3. 공연 목록 검색
4. 공연 상세 조회
5. 관심 공연/볼 예정 공연 등록
6. 마이페이지에서 관심/볼 예정/내 게시글 확인
7. 게시글 작성 및 댓글 작성
8. 에디터 이미지 업로드
9. AI 추천 요청
   - `가족과 보기 좋은 공연 추천해줘`
   - `시간 없을 때 보기 좋은 공연 추천해줘`
   - `10만원 이하로 볼만한 공연 추천해줘`
10. 추천 피드백 저장

## 주의 사항

- 실제 `.env`, DB 비밀번호, API Key는 Git에 올리지 않습니다.
- OpenAI/GMS quota 부족 시 rule-based fallback 응답이 반환될 수 있습니다.
- KOPIS 데이터가 RDS에 없으면 검색 결과는 `total: 0`으로 정상 응답됩니다.
- 한국음악/국악 데이터는 KOPIS `CCCC` 장르 적재가 필요합니다.
- 세종은 `sido=세종특별자치시`, `gugun=""`이 허용됩니다.
- 해외 공연장은 국내 지역 필터 대상이 아니므로 `sido/gugun`이 비어 있을 수 있습니다.
- S3 환경변수가 컨테이너에 전달되지 않으면 이미지 URL이 `/media/...`로 내려가 운영에서 404가 날 수 있습니다.

