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
- 이메일 비밀번호 재설정 및 가입 방식 안내
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
- Tiptap HTML 서버 허용 목록 정제 및 과거 데이터 응답 정제
- S3 이미지 저장

### 운영

- AWS Elastic Beanstalk Docker 배포
- RDS PostgreSQL
- ElastiCache Valkey Redis
- Celery worker/beat
- S3 media storage
- `/health/` liveness 헬스 체크
- `/health/ready/` database·Redis readiness 체크
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
├── FRONTEND_HANDOFF.md
└── README.md
```

Codex 대화 기록 플러그인은 `plugins/workspace-conversation-log/`에 있으며, 원본이 아닌
검수 완료 학습 데이터는 백엔드와 같은 상위 폴더의 독립 저장소
`../culturepick-training-data/`에서 관리합니다.

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

의존성 준비 상태는 다음 엔드포인트로 확인합니다.

```http
GET http://127.0.0.1:8000/health/ready/
```

DB 또는 Redis가 준비되지 않으면 `503`을 반환합니다.

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

두 형식을 하나로 통합할 필요는 없습니다. 이 프로젝트는 값이 있는
`DATABASE_URL`을 우선 사용하고, URL이 없을 때 `DB_*`를 사용합니다. 한 환경에
두 형식의 실제 값을 동시에 두면 운영자가 수정한 값과 Django가 읽는 값이 달라질
수 있으므로 다음처럼 분리합니다.

- 로컬 Docker: `DATABASE_URL`만 사용
- Elastic Beanstalk/RDS: `DB_*`만 사용하고 EB 환경 속성의 `DATABASE_URL`은 삭제

로컬 예시:

```env
DATABASE_URL=postgresql://postgres:postgres@db:5432/culturepick
```

AWS 예시:

```env
DB_NAME=culturepick
DB_USER=your-rds-user
DB_PASSWORD=your-rds-password
DB_HOST=your-rds-endpoint
DB_PORT=5432
```

DB 비밀번호를 URL로 조합하지 않는 AWS 방식은 `@`, `:`, `/`, `%` 같은 문자의 URL
인코딩 실수를 피할 수 있다는 장점도 있습니다. 실제 RDS 비밀번호의 유효성은 EB
인스턴스/VPC 안에서 `python manage.py check` 또는 readiness endpoint로 검증하고,
로컬 접속 timeout은 비밀번호 오류가 아니라 Security Group·라우팅 단계의 실패일 수
있습니다.

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
CACHE_URL=rediss://your-valkey-endpoint:6379/0
CACHE_KEY_PREFIX=culturepick-cache
DRF_NUM_PROXIES=1
CELERY_BROKER_URL=rediss://your-valkey-endpoint:6379/0
CELERY_RESULT_BACKEND=django-db
CELERY_ENABLE_KOPIS_BEAT_SCHEDULE=False
CELERY_WORKER_ENABLE_REMOTE_CONTROL=False
CELERY_REDIS_GLOBAL_KEYPREFIX={culturepick-celery}:
CELERY_REDIS_RESULT_GLOBAL_KEYPREFIX={culturepick-celery-result}:
LOG_RAW_RETENTION_DAYS=90
LOG_RETENTION_BATCH_SIZE=1000
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
COMMUNITY_ALLOWED_IMAGE_HOSTS=your-bucket-name.s3.ap-northeast-2.amazonaws.com
```

운영에서는 access key를 직접 넣기보다 Elastic Beanstalk EC2 IAM Role 권한 사용을 권장합니다.
`AWS_S3_CUSTOM_DOMAIN` 또는 기본 S3 호스트는 서버 이미지 허용 목록에 자동으로
추가됩니다. CloudFront를 붙이거나 별도 CDN을 쓰면 그 호스트를
`COMMUNITY_ALLOWED_IMAGE_HOSTS`에 쉼표로 추가합니다.

### 이메일/계정 복구

로컬은 `console` 이메일 backend를 사용합니다. 운영에서는 AWS SES SMTP 또는 사용하는
메일 서비스의 SMTP 자격 증명을 Elastic Beanstalk 환경 속성에 설정해야 실제 메일이
발송됩니다.

```env
DEFAULT_FROM_EMAIL=noreply@culturepick.net
EMAIL_HOST=email-smtp.ap-northeast-2.amazonaws.com
EMAIL_PORT=587
EMAIL_HOST_USER=your-smtp-user
EMAIL_HOST_PASSWORD=your-smtp-password
EMAIL_USE_TLS=True
EMAIL_TIMEOUT=10
FRONTEND_PASSWORD_RESET_URL=https://culturepick.netlify.app/find-account
FRONTEND_LOGIN_URL=https://culturepick.netlify.app/login
PASSWORD_RESET_TIMEOUT=3600
PASSWORD_RESET_REQUEST_THROTTLE_RATE=5/hour
PASSWORD_RESET_CONFIRM_THROTTLE_RATE=10/hour
ACCOUNT_RECOVERY_THROTTLE_RATE=5/hour
```

`FRONTEND_PASSWORD_RESET_URL` 페이지는 메일 링크의 `uid`, `token` query parameter를
읽어 `/api/v1/auth/password/reset/confirm/`에 전달해야 합니다. 현재 백엔드는 이 계약을
제공하지만 프론트엔드 페이지 구현은 별도 작업입니다. SES sandbox를 사용하는 동안에는
발신 주소와 수신 주소 검증 제한도 함께 확인해야 합니다.

메일 요청 API는 가입 여부에 따른 SMTP 응답 시간 차이를 만들지 않도록 모든 요청을
Celery에 전달하고 worker에서 계정 조회와 발송을 수행합니다. 따라서 운영에서는
`celery-worker`와 broker가 함께 정상이어야 실제 메일이 도착합니다. IP 제한은
운영의 공유 Redis cache를 사용하며, `DRF_NUM_PROXIES=1`은 현재 직접 ALB→EB 구성에
맞춘 값입니다. CloudFront 같은 프록시 계층을 추가하면 실제 신뢰 체인을 확인한 뒤
그 값을 조정해야 합니다.

### CORS/CSRF

```env
CORS_ALLOWED_ORIGINS=https://culturepick.netlify.app
CSRF_TRUSTED_ORIGINS=https://culturepick.netlify.app
```

Netlify 주소 끝에는 `/`를 붙이지 않습니다.

### HTTPS 확인

프론트가 `https://culturepick.netlify.app`이므로 운영 API도 HTTPS여야 합니다. EB
기본 CNAME에 HTTP만 열려 있으면 브라우저가 mixed content 요청을 차단합니다.

1. Elastic Beanstalk → Environment → Configuration → Capacity에서 환경이
   `Load balanced`인지 확인합니다.
2. Configuration → Load balancer → Listeners에 `443 / HTTPS`가 있는지 확인합니다.
3. 443 listener에 소유한 API 도메인용 ACM 인증서가 연결됐는지, 로드밸런서 보안
   그룹에 TCP 443 inbound가 있는지 확인합니다.
4. target group의 `/health/`가 healthy인지 확인한 뒤 HTTP 80을 HTTPS로 redirect합니다.
5. 외부에서 HTTP가 `301/308`, HTTPS `/health/`가 `200`, 인증서 SAN이 접속 도메인과
   일치하는지 확인합니다.

`culturepick.ap-northeast-2.elasticbeanstalk.com`은 AWS 소유 이름이라 이 이름으로
사용자 ACM 인증서를 발급할 수 없습니다. 가능한 방식은 하나가 아니라 아래 두 가지입니다.

```text
A. 보유 도메인 사용
브라우저 → https://api.<보유도메인> → ALB + ACM → EB의 HTTP:80

B. 보유 도메인 없이 CloudFront 사용
브라우저 → https://dxxxxxxxx.cloudfront.net → CloudFront → EB의 HTTP:80
```

A는 장기 운영 권장안이지만 EB 환경이 `Load balanced`여야 하고 API에 사용할 도메인을
직접 소유해야 합니다. `culturepick.netlify.app`은 Netlify가 소유한 도메인이므로
`api.culturepick.netlify.app` 인증서를 CulturePick이 발급할 수 없습니다. B는 별도
도메인이 없어도 CloudFront 기본 HTTPS 주소를 바로 사용할 수 있고 single-instance
EB도 origin으로 둘 수 있지만, API 앞에 CloudFront 설정이 한 계층 추가됩니다.

인스턴스의 Nginx/Gunicorn에 인증서를 직접 설치하는 세 번째 기술적 방법도 있으나 인증서
갱신과 인스턴스 교체 대응을 직접 관리해야 하므로 현재 운영안으로 권장하지 않습니다.
TLS가 실제로 확인되기 전에 HSTS나 Django SSL redirect를 먼저 켜면 health check 또는
접속이 깨질 수 있습니다.

## 프론트 연동 요약

자세한 API 요청/응답은 [API.md](./API.md)에, 프론트 담당자의 구현 체크리스트는
[FRONTEND_HANDOFF.md](./FRONTEND_HANDOFF.md)에 정리되어 있습니다.

프론트에서 특히 주의할 점:

- API base URL은 최종 결정된 HTTPS API 주소 사용
- 인증 API 응답의 access token을 `Authorization: Bearer <access_token>`으로 전달
- access token 만료 시 `/api/v1/auth/token/refresh/` 호출
- 계정 찾기 화면에서 재설정 메일 요청·확정 및 가입 방식 안내 API 연동
- 게시판 카테고리 요청값은 영어 저장값 사용
- 에디터 이미지는 `/api/v1/community/images/`에 multipart 업로드 후 `url` 또는 `image_url`을 본문에 삽입
- 공연 상세/관심/볼예정 API는 `performance_id` 사용
- 관심/볼예정 버튼은 `is_interested`, `is_watchlisted` 응답값으로 UI 갱신
- 추천 API는 로그인 필요
- 추천 피드백 저장 시 `session_id` 보관
- CORS origin에는 trailing slash를 넣지 않음
- 게시판 HTML은 서버에서도 정제하지만, 프론트에서도 DOMPurify 등으로 방어 계층을 유지

## 커뮤니티 HTML 안전 정책

`content_format=html`인 게시글은 생성과 수정 시 서버에서 허용 목록 기반으로
정제한 뒤 저장합니다. 허용 범위는 Tiptap 기본 본문 요소와 `a[href]`,
`img[src,alt,title]`이며 이벤트 핸들러, `style`, `class`, `id`, 스크립트성
태그 및 `javascript:`/`data:` URL은 제거합니다. 정제 후 보이는 텍스트나
안전한 이미지가 없으면 저장을 거부합니다. Markdown 본문은 HTML 정제 대상이
아닙니다.

이미지 `src`는 로컬 업로드 경로인 `/media/` 또는
`COMMUNITY_ALLOWED_IMAGE_HOSTS`에 등록된 호스트의 HTTPS URL만 유지합니다. HTTP,
protocol-relative URL, 다른 외부 호스트, 사용자 정보가 포함된 URL, `/media/../`
형식의 경로 순회 값은 제거합니다. 링크 `href`는 별도 정책으로 상대 URL과
`http`/`https`/`mailto`를 허용합니다.

기존 HTML 데이터는 API 응답 시 안전하게 정제되지만 자동으로 DB를 덮어쓰지
않습니다. 운영 데이터 정리가 필요하면 먼저 읽기 전용 점검을 실행합니다.

```bash
python manage.py sanitize_community_html
```

출력의 `changed`, `manual_review`와 게시글 ID를 확인한 다음 명시적으로
적용합니다. 정제 후 빈 본문이 되는 행은 `--apply`에서도 변경하지 않고 수동
검토 대상으로 남깁니다.

```bash
python manage.py sanitize_community_html --apply
```

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

운영의 Django cache도 `CACHE_URL`을 통해 같은 Redis/Valkey를 사용하되
`CACHE_KEY_PREFIX`로 Celery 키와 분리합니다. 이 공유 cache가 복구 API의 DRF 요청
제한을 모든 Gunicorn worker와 EB 인스턴스에 동일하게 적용합니다. `LocMemCache`로
되돌리면 worker/인스턴스마다 제한 횟수가 따로 계산되므로 운영에 사용하지 마세요.

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

이 명령은 `update_or_create` 방식이라 같은 RDS에 다시 실행해도 중복 일정을 만들지
않습니다. 일정은 `django_celery_beat` 테이블에 남으므로 일반 재배포 때는 유지되고,
RDS 교체·초기화 후에 다시 등록하면 됩니다. DB 스케줄을 사용할 때는
`CELERY_ENABLE_KOPIS_BEAT_SCHEDULE=False`를 유지해 코드 스케줄과 중복 실행되지 않게
합니다.

등록되는 작업:

```text
daily-sync-ongoing-performances  -> 매일 04:10 Asia/Seoul
daily-sync-upcoming-performances -> 매일 04:30 Asia/Seoul
```

원본 로그 90일 보존 스케줄 등록:

```bash
sudo docker exec -it current-web-1 python manage.py setup_log_retention_schedule
```

이 명령도 `update_or_create` 방식이며, 기본적으로 매일 03:30 Asia/Seoul에 실행됩니다.
만료된 검색·조회·Q&A 원문은 사용자 ID와 자유 텍스트를 제외한 일별 집계로 먼저 보존한
뒤 배치 삭제합니다. 실행 전에 삭제 대상을 확인하려면 dry-run 기본 명령을 사용합니다.

```bash
sudo docker exec -it current-web-1 python manage.py prune_expired_logs
```

수동으로 실제 반영할 때만 `--apply`를 붙입니다. Celery 작업은 공유 Redis 잠금으로
중복 실행을 막습니다.

현재 Compose는 EB 인스턴스마다 `celery-beat`를 실행합니다. 환경을 자동 확장하면 여러
beat가 같은 작업을 발행할 수 있으므로, 단일 인스턴스가 아니라면 scheduler를 한 곳에만
두는 배포 구조로 바꿔야 합니다.

등록 확인:

```bash
sudo docker exec -it current-web-1 python manage.py shell -c "from django_celery_beat.models import PeriodicTask; print(list(PeriodicTask.objects.filter(name__in=['daily-prune-expired-logs','daily-sync-ongoing-performances','daily-sync-upcoming-performances','celery.backend_cleanup']).values('name','task','enabled','crontab__hour','crontab__minute','crontab__timezone')))"
```

### PostgreSQL 부분 문자열 검색 인덱스

공연명·출연진·장르·공연장명·지역/주소와 게시글 제목/본문의 `icontains` 검색에는
`pg_trgm` 확장과 GIN 표현식 인덱스를 사용합니다. 마이그레이션은 PostgreSQL에서만
확장과 인덱스를 만들고 SQLite 테스트에서는 건너뜁니다. 운영 테이블의 쓰기 중단을
줄이기 위해 인덱스는 `CONCURRENTLY`로 생성됩니다.

배포 후 확인:

```bash
sudo docker exec -it current-web-1 python manage.py shell -c "from django.db import connection; c=connection.cursor(); c.execute(\"SELECT extname FROM pg_extension WHERE extname='pg_trgm'\"); print(c.fetchall()); c.execute(\"SELECT indexname FROM pg_indexes WHERE indexname LIKE '%trgm_gin' ORDER BY indexname\"); print(c.fetchall())"
```

짧은 한두 글자 검색이나 데이터가 매우 적은 개발 DB에서는 PostgreSQL이 인덱스보다
순차 조회가 더 싸다고 판단할 수 있습니다. 대량 운영 데이터에서 `EXPLAIN
(ANALYZE, BUFFERS)`로 실제 실행 계획을 확인해야 최적화 효과를 판단할 수 있습니다.

### 검수된 학습 후보 내보내기

자동 점수만 높은 후보는 내보내지 않습니다. Django Admin에서 담당자가 내용을 확인하고
승인해 `reviewed_by`, `reviewed_at`이 기록된 후보만 비식별화한 뒤 형제 저장소로
내보냅니다.

```bash
python manage.py export_recommendation_training_data \
  --output-dir ../culturepick-training-data \
  --dataset-version 2026-07-23-v1

python manage.py export_recommendation_training_data \
  --output-dir ../culturepick-training-data \
  --dataset-version 2026-07-23-v1 \
  --apply
```

첫 명령은 dry-run이며 파일이나 DB를 바꾸지 않습니다. 두 번째 명령만 버전별
`data.jsonl`과 SHA-256 매니페스트를 만들고 해당 후보를 exported 상태로 바꿉니다.
원본 Codex 대화 로그를 이 경로로 직접 복사하지 않습니다.

로컬 Docker Compose의 `web` 컨테이너에는 형제 저장소가
`/culturepick-training-data`로 마운트됩니다. Docker 안에서 실행할 때는
`--output-dir /culturepick-training-data`를 사용합니다.

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

