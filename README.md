# CulturePick BE

공연 예술 통합 정보 서비스 **컬쳐픽** 백엔드 레포지토리입니다.

공연예술통합전산망(KOPIS) API를 기반으로 공연 데이터를 수집·제공하며, JWT 인증 및 소셜 로그인(카카오·네이버·구글)을 지원합니다.

---

## 기술 스택

| 분류 | 기술 |
|---|---|
| Framework | Django 5.1 |
| Database | PostgreSQL 16 |
| Async | Celery + Redis |
| Infra | Docker |
| Auth | JWT (SimpleJWT), OAuth2 |
| Data | KOPIS OpenAPI |

---

## 주요 기능

- 공연 데이터 검색 (키워드·장르·지역·날짜)
- 공연 상세 정보 및 예매 링크 제공
- JWT 기반 로그인·회원가입
- 소셜 로그인 (카카오·네이버·구글)
- 관심 공연 저장 및 관람 기록
- 채팅 기반 AI 공연 추천
- KOPIS 데이터 주기적 자동 업데이트 (Celery Beat)

---

## 프로젝트 구조

```
culturepick_BE/
├── BE/                     # 프로젝트 설정
│   └── settings/
│       ├── base.py
│       ├── local.py
│       └── production.py
├── apps/
│   ├── users/              # 유저 & 인증
│   ├── performances/       # 공연 데이터 + KOPIS 연동
│   │   └── kopis/
│   └── logs/               # 검색·클릭·AI 로그
├── common/                 # 공통 유틸리티
├── fixtures/               # 샘플 데이터
├── docker/
├── requirements/
│   ├── base.txt
│   ├── local.txt
│   └── production.txt
└── docker-compose.yml
```

---

## 로컬 개발 환경 세팅

### 사전 요구사항

- Python 3.11
- Docker Desktop

### 1. 레포지토리 클론

```bash
git clone https://github.com/{팀명}/culturepick-be.git
cd culturepick-be
```

### 2. 가상환경 생성 및 패키지 설치

```bash
python -m venv venv
source venv/Scripts/activate  # Windows
# source venv/bin/activate    # Mac/Linux

pip install -r requirements/local.txt
```

### 3. 환경변수 설정

```bash
cp .env.example .env
```

`.env` 파일을 열어서 아래 항목을 채워주세요.

```
DJANGO_SECRET_KEY=임의의_시크릿_키
KOPIS_API_KEY=KOPIS에서_발급받은_API_키
```

### 4. Docker로 DB 실행

```bash
docker compose up -d db
```

### 5. 마이그레이션

```bash
python manage.py migrate
```

### 6. 서버 실행

```bash
python manage.py runserver
```

---

## 샘플 데이터 적재 (프론트 개발용)

```bash
python manage.py loaddata fixtures/venues_sample.json
python manage.py loaddata fixtures/performances_sample.json
```

장르별 공연 20건씩, 총 100건의 샘플 데이터가 적재됩니다.

---

## KOPIS 데이터 수집

### 초기 전체 적재 (최초 1회)

```bash
# 공연시설 먼저 수집 후 전체 공연 수집
python manage.py sync_kopis --with-venues
```

### 특정 기간·장르만 수집

```bash
# 뮤지컬만, 특정 기간
python manage.py sync_kopis --stdate 20260101 --eddate 20260531 --genre GGGA
```

| 장르코드 | 장르명 |
|---|---|
| AAAA | 연극 |
| GGGA | 뮤지컬 |
| CCCA | 서양음악(클래식) |
| CCCD | 대중음악 |
| BBBC | 무용 |

### 자동 업데이트 (Celery Beat)

매일 새벽 4시에 공연중·공연예정 데이터를 자동으로 갱신합니다.

```bash
# Celery 워커 실행
celery -A config worker -l info

# Celery Beat 스케줄러 실행
celery -A config beat -l info
```

---

## API 엔드포인트

### 인증

| Method | URL | 설명 |
|---|---|---|
| POST | `/api/v1/auth/register/` | 회원가입 |
| POST | `/api/v1/auth/login/` | 로그인 |
| POST | `/api/v1/auth/logout/` | 로그아웃 |
| POST | `/api/v1/auth/token/refresh/` | 액세스 토큰 갱신 |
| POST | `/api/v1/auth/social/` | 소셜 로그인 (카카오·네이버·구글) |

### 공연

| Method | URL | 설명 |
|---|---|---|
| GET | `/api/v1/performances/` | 공연 목록 검색 |
| GET | `/api/v1/performances/{id}/` | 공연 상세 |

---

## 환경변수 목록

| 변수명 | 설명 | 필수 |
|---|---|---|
| DJANGO_SECRET_KEY | Django 시크릿 키 | O |
| DJANGO_DEBUG | 디버그 모드 (True/False) | O |
| DATABASE_URL | PostgreSQL 연결 URL | O |
| REDIS_URL | Redis 연결 URL | O |
| KOPIS_API_KEY | KOPIS OpenAPI 키 | O |
| KAKAO_CLIENT_ID | 카카오 REST API 키 | 소셜 로그인 사용 시 |
| NAVER_CLIENT_ID | 네이버 클라이언트 ID | 소셜 로그인 사용 시 |
| NAVER_CLIENT_SECRET | 네이버 클라이언트 시크릿 | 소셜 로그인 사용 시 |
| GOOGLE_CLIENT_ID | 구글 클라이언트 ID | 소셜 로그인 사용 시 |
| GOOGLE_CLIENT_SECRET | 구글 클라이언트 시크릿 | 소셜 로그인 사용 시 |
