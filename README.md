# CulturePick BE

공연 예술 통합 정보 서비스 **컬쳐픽** 백엔드 레포지토리입니다.

공연예술통합전산망(KOPIS) API를 기반으로 공연 데이터를 수집·제공하며, JWT 인증 및 소셜 로그인, 공연 검색, 관심/볼예정, 사용자 활동 로그 기능을 지원합니다.

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

- JWT 기반 회원가입·로그인·로그아웃
- 소셜 로그인 (구글·네이버)
- 공연 목록 및 통합 검색
- 장르·지역·상태 기반 공연 검색
- 공연 상세 정보 및 예매 링크 제공
- 관심 공연 및 볼예정 공연 저장
- 검색·조회·행동·QnA 로그 저장
- KOPIS 데이터 수집 및 로컬 샘플 데이터 적재

---

## 프로젝트 구조

```text
culturepick-back/
├── BE/                     # Django 프로젝트 설정
│   └── settings/
│       ├── base.py
│       ├── local.py
│       └── production.py
├── apps/
│   ├── users/              # 유저 & 인증
│   ├── performances/       # 공연 데이터 + KOPIS 연동
│   └── logs/               # 검색·조회·행동·QnA 로그
├── common/                 # 공통 유틸리티
├── fixtures/               # 프론트 연동 검증용 샘플 데이터
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
- Git Bash 또는 PowerShell

### 1. 레포지토리 클론

```bash
git clone https://github.com/big20261028/culturepick-back.git
cd culturepick-back
```

### 2. 가상환경 생성 및 패키지 설치

Git Bash:

```bash
python -m venv .venv
source .venv/Scripts/activate
pip install -r requirements/local.txt
```

PowerShell:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements/local.txt
```

### 3. 환경변수 설정

```bash
cp .env.example .env
```

`.env` 파일에 필요한 값을 설정합니다.

```env
DJANGO_SECRET_KEY=your-secret-key
DJANGO_DEBUG=True
DJANGO_ALLOWED_HOSTS=localhost,127.0.0.1
DJANGO_SETTINGS_MODULE=BE.settings.local

DATABASE_URL=postgresql://postgres:postgres@localhost:5432/culturepick
REDIS_URL=redis://localhost:6379/0

KOPIS_API_KEY=your-kopis-api-key

GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
NAVER_CLIENT_ID=your-naver-client-id
NAVER_CLIENT_SECRET=your-naver-client-secret
```

### 4. Docker로 DB 실행

```bash
docker compose up -d db redis
```

### 5. 마이그레이션

```bash
python manage.py migrate
```

### 6. 서버 실행

```bash
python manage.py runserver
```

로컬 서버 주소:

```text
http://127.0.0.1:8000
```

---

## 로컬 데이터 적재

프론트 연동 검증용 샘플 fixture가 준비되어 있습니다.

샘플은 공연 목록, 통합 검색, 장르/지역/상태 필터, 상세 페이지, 관심/볼예정 토글 검증이 가능하도록 구성되어 있습니다.

### 샘플 구성

| 파일 | 설명 | 개수 |
|---|---|---:|
| `fixtures/venues_sample.json` | 공연장 | 8 |
| `fixtures/performances_sample.json` | 공연 | 12 |
| `fixtures/performance_images_sample.json` | 공연 상세 이미지 | 12 |
| `fixtures/booking_links_sample.json` | 예매 링크 | 12 |

### 적재 순서

```bash
python manage.py loaddata fixtures/venues_sample.json
python manage.py loaddata fixtures/performances_sample.json
python manage.py loaddata fixtures/performance_images_sample.json
python manage.py loaddata fixtures/booking_links_sample.json
```

### 샘플 검색어

```text
햄릿
레미제라블
헬로카봇
재즈
제주
```

### 샘플 공연 ID

```text
PF900001  햄릿
PF900002  레미제라블
PF900003  헬로카봇 스페셜: 전설의 용사를 찾아서
PF900010  제주 인디 콘서트
```

샘플 데이터는 프론트 연동 확인용 고정 데이터입니다. 기존 KOPIS 데이터가 많이 적재된 DB에 섞기보다는, 비어 있는 개발 DB에서 사용하는 것을 권장합니다.

---

## KOPIS 데이터 수집

### 전체 수집

```bash
python manage.py sync_kopis --with-venues --stdate 20260101 --eddate 20261231
```

### 특정 기간·장르만 수집

```bash
python manage.py sync_kopis --with-venues --genre GGGA --stdate 20260101 --eddate 20261231
```

| 장르코드 | 장르명 |
|---|---|
| AAAA | 연극 |
| GGGA | 뮤지컬 |
| CCCA | 서양음악(클래식) |
| CCCC | 한국음악(국악) |
| CCCD | 대중음악 |
| BBBC | 무용 |

---

## API 엔드포인트

API prefix:

```text
/api/v1
```

### 인증

| Method | URL | 설명 |
|---|---|---|
| POST | `/api/v1/auth/register/` | 회원가입 |
| POST | `/api/v1/auth/login/` | 로그인 |
| POST | `/api/v1/auth/logout/` | 로그아웃 |
| POST | `/api/v1/auth/token/refresh/` | 액세스 토큰 갱신 |
| POST | `/api/v1/auth/social/` | 소셜 로그인 |

### 공연

| Method | URL | 설명 |
|---|---|---|
| GET | `/api/v1/performances/` | 공연 목록/검색 |
| GET | `/api/v1/performances/{performance_id}/` | 공연 상세 |
| POST | `/api/v1/performances/{performance_id}/actions/` | 관심/볼예정 토글 |

### 로그

| Method | URL | 설명 |
|---|---|---|
| POST | `/api/v1/logs/search/` | 검색 로그 저장 |
| POST | `/api/v1/logs/view/` | 조회/행동 로그 저장 |
| POST | `/api/v1/logs/qna/` | QnA/AI 추천 로그 저장 |

---

## 주요 Query Parameter

공연 목록/검색 API에서 사용하는 주요 파라미터입니다.

| 이름 | 설명 | 예시 |
|---|---|---|
| `keyword` | 통합 검색어 | `햄릿` |
| `genre` | 장르 필터 | `musical` |
| `local` | 지역 필터 | `seoul` |
| `status` | 공연 상태 | `performing` |
| `pageNum` | 페이지 번호 | `1` |
| `pageSize` | 페이지 크기 | `10` |
| `sorted` | 정렬 | `latest` |

통합 검색은 공연명, 출연진, 공연장을 기준으로 우선순위를 계산합니다.

```text
공연명 일치: +100
출연진 일치: +60
공연장 일치: +40
```

---

## 소셜 로그인 참고

현재 프론트 연동 검증이 완료된 provider는 아래와 같습니다.

```text
google
naver
```

프론트 callback URI는 아래 형태로 통일합니다.

```text
http://localhost:5173/auth/callback/google
http://localhost:5173/auth/callback/naver
```

카카오는 이메일 권한 및 비즈 앱 설정 이슈가 있어 현재 프론트 연동 대상에서 제외합니다.

---

## 환경변수 목록

| 변수명 | 설명 | 필수 |
|---|---|---|
| DJANGO_SECRET_KEY | Django 시크릿 키 | O |
| DJANGO_DEBUG | 디버그 모드 | O |
| DJANGO_ALLOWED_HOSTS | 허용 호스트 | O |
| DJANGO_SETTINGS_MODULE | Django settings module | O |
| DATABASE_URL | PostgreSQL 연결 URL | O |
| REDIS_URL | Redis 연결 URL | O |
| KOPIS_API_KEY | KOPIS OpenAPI 키 | O |
| GOOGLE_CLIENT_ID | 구글 클라이언트 ID | 소셜 로그인 사용 시 |
| GOOGLE_CLIENT_SECRET | 구글 클라이언트 시크릿 | 소셜 로그인 사용 시 |
| NAVER_CLIENT_ID | 네이버 클라이언트 ID | 소셜 로그인 사용 시 |
| NAVER_CLIENT_SECRET | 네이버 클라이언트 시크릿 | 소셜 로그인 사용 시 |

