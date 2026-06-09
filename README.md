# CulturePick Backend API

이 README는 프론트엔드 API 연동을 위한 임시 문서입니다.  
프로젝트 완성 후 서비스 소개, 배포 방식, 아키텍처 문서는 다시 정리할 예정입니다.

## 기본 정보

로컬 서버:

```text
http://127.0.0.1:8000
```

API prefix:

```text
/api/v1
```

Postman 환경 변수 추천:

```text
base_url=http://127.0.0.1:8000/api/v1
access_token=로그인 후 받은 access token
refresh_token=로그인 후 받은 refresh token
performance_id=공연 ID 예: PF123456
```

인증이 필요한 API는 아래 헤더를 사용합니다.

```http
Authorization: Bearer {{access_token}}
Content-Type: application/json
```

## 공통 응답/에러

대부분의 API는 JSON을 반환합니다.

DRF validation error는 보통 아래 형태입니다.

```json
{
  "field_name": ["error message"]
}
```

인증이 필요한 API에서 토큰이 없거나 유효하지 않으면 `401 Unauthorized`가 반환됩니다.

## 인증 API

### 회원가입

```http
POST {{base_url}}/auth/register/
```

Request:

```json
{
  "email": "user@example.com",
  "password": "ValidPass123!",
  "password_confirm": "ValidPass123!",
  "nickname": "컬처픽"
}
```

Response `201`:

```json
{
  "message": "회원가입이 완료되었습니다."
}
```

비밀번호는 Django 기본 비밀번호 검증을 통과해야 합니다.

### 로그인

```http
POST {{base_url}}/auth/login/
```

Request:

```json
{
  "email": "user@example.com",
  "password": "ValidPass123!"
}
```

Response `200`:

```json
{
  "access": "jwt_access_token",
  "refresh": "jwt_refresh_token"
}
```

### 로그아웃

```http
POST {{base_url}}/auth/logout/
Authorization: Bearer {{access_token}}
```

Request:

```json
{
  "refresh": "{{refresh_token}}"
}
```

Response `200`:

```json
{
  "message": "로그아웃 되었습니다."
}
```

### 토큰 재발급

```http
POST {{base_url}}/auth/token/refresh/
```

Request:

```json
{
  "refresh": "{{refresh_token}}"
}
```

Response `200`:

```json
{
  "access": "new_access_token",
  "refresh": "new_refresh_token"
}
```

`ROTATE_REFRESH_TOKENS=True` 설정이므로 refresh token도 새로 내려올 수 있습니다. 새 refresh token을 저장해 주세요.

## 소셜 로그인 API

백엔드는 프론트가 받은 OAuth `code`를 전달받아 소셜 provider와 토큰 교환을 수행합니다.

```http
POST {{base_url}}/auth/social/
```

현재 실제 검증 완료:

```text
Google: 완료
Naver: 완료
Kakao: 이메일 권한/비즈 앱 이슈로 프론트 연동 대상에서 제외 예정
```

### Google

프론트 callback URI:

```text
http://localhost:5173/auth/callback/google
```

프론트는 callback URL의 `code` 값을 읽어 백엔드에 전달합니다.

Request:

```json
{
  "provider": "google",
  "code": "google_callback_code",
  "redirect_uri": "http://localhost:5173/auth/callback/google"
}
```

Response `200`:

```json
{
  "message": "회원가입 완료",
  "access": "jwt_access_token",
  "refresh": "jwt_refresh_token"
}
```

이미 가입된 소셜 계정이면 message는 `"로그인 성공"`입니다.

### Naver

프론트 callback URI:

```text
http://localhost:5173/auth/callback/naver
```

네이버는 `code`와 `state`를 함께 전달해야 합니다.

Request:

```json
{
  "provider": "naver",
  "code": "naver_callback_code",
  "redirect_uri": "http://localhost:5173/auth/callback/naver",
  "state": "naver_callback_state"
}
```

Response `200`:

```json
{
  "message": "회원가입 완료",
  "access": "jwt_access_token",
  "refresh": "jwt_refresh_token"
}
```

### Kakao 참고

백엔드 코드는 `provider: "kakao"` 요청을 처리할 수 있게 되어 있습니다.  
다만 현재 카카오 앱에서 이메일 권한 사용이 어렵기 때문에 프론트 연동 우선순위에서는 제외합니다.

카카오를 다시 사용하게 되면 callback URI는 아래로 통일합니다.

```text
http://localhost:5173/auth/callback/kakao
```

카카오 이메일이 없을 경우 백엔드는 내부용 이메일을 생성합니다.

```text
kakao_{kakao_id}@social.culturepick.local
```

실제 계정 식별은 `provider = kakao`, `provider_id = 카카오 id` 기준입니다.

## 공연 API

### 공연 목록/검색

```http
GET {{base_url}}/performances/
```

Query params:

| 이름 | 설명 | 예시 |
| --- | --- | --- |
| `keyword` | 통합 검색어 | `레미제라블` |
| `genre` | 장르 필터. 쉼표로 복수 전달 가능 | `musical`, `play`, `classic`, `concert`, `dancing` |
| `local` | 지역 필터. `region`도 허용 | `seoul`, `gyeonggi`, `busan` |
| `status` | 공연 상태 | `upcoming`, `performing`, `done` |
| `sorted` | 정렬. `sort`도 허용 | `latest`, `start_date`, `title`, `popular`, `zzim` |
| `pageNum` | 페이지 번호 | `1` |
| `pageSize` | 페이지 크기. 최대 100 | `20` |

통합 검색 점수:

```text
공연명 일치: +100
출연진 일치: +60
공연장 일치: +40
```

예시:

```http
GET {{base_url}}/performances/?keyword=햄릿&pageNum=1&pageSize=20
```

```http
GET {{base_url}}/performances/?genre=musical&local=seoul&status=upcoming&sorted=latest&pageNum=1&pageSize=20
```

Response `200`:

```json
{
  "pageNum": 1,
  "pageSize": 20,
  "total": 1,
  "searchData": [
    {
      "performance_id": "PF123456",
      "title": "공연명",
      "genre": "뮤지컬",
      "genre_code": "GGGA",
      "start_date": "2026-06-01",
      "end_date": "2026-06-30",
      "status": "공연예정",
      "status_code": "01",
      "poster_url": "https://example.com/poster.jpg",
      "runtime": "120분",
      "age_rating": "8세 이상",
      "min_price": 30000,
      "max_price": 120000,
      "is_free": false,
      "openrun": false,
      "is_child": false,
      "is_festival": false,
      "venue": {
        "venue_id": "FC123456",
        "name": "공연장명",
        "sido": "서울",
        "gugun": "종로구",
        "address": "서울특별시 ...",
        "latitude": "37.0000000",
        "longitude": "127.0000000"
      },
      "view_count": 0,
      "zzim_count": 0,
      "search_score": 100
    }
  ],
  "page": 1,
  "page_size": 20,
  "results": [
    {
      "performance_id": "PF123456",
      "...": "searchData와 동일한 객체 구조"
    }
  ]
}
```

프론트에서는 `searchData`를 우선 사용하면 됩니다. `results`는 호환용으로 같은 데이터가 들어갑니다.

### 공연 상세

```http
GET {{base_url}}/performances/{{performance_id}}/
```

인증 없이 호출 가능하지만, 로그인 사용자가 호출하면 `is_interested`, `is_watchlisted`가 해당 사용자 기준으로 계산됩니다.  
인증 헤더가 없으면 둘 다 `false`입니다.

Response 주요 필드:

```json
{
  "performance_id": "PF123456",
  "title": "공연명",
  "genre": "뮤지컬",
  "genre_code": "GGGA",
  "start_date": "2026-06-01",
  "end_date": "2026-06-30",
  "status": "공연예정",
  "status_code": "01",
  "cast": "출연진",
  "crew": "제작진",
  "runtime": "120분",
  "age_rating": "8세 이상",
  "synopsis": "공연 줄거리",
  "price_info": "R석 120,000원",
  "min_price": 30000,
  "max_price": 120000,
  "is_free": false,
  "schedule_info": "화-금 19:30",
  "poster_url": "https://example.com/poster.jpg",
  "venue": {},
  "images": [],
  "booking_links": [],
  "view_count": 1,
  "zzim_count": 0,
  "is_interested": false,
  "is_watchlisted": false
}
```

상세 조회 시 백엔드에서 `view_count`가 1 증가하고, 조회 로그가 자동 저장됩니다.

### 관심/볼예정 토글

```http
POST {{base_url}}/performances/{{performance_id}}/actions/
Authorization: Bearer {{access_token}}
```

`action_type`:

```text
interest = 관심/찜
watchlist = 볼예정
```

토글 방식:

```json
{
  "action_type": "interest"
}
```

현재 상태를 명시하는 방식:

```json
{
  "action_type": "watchlist",
  "is_active": true
}
```

```json
{
  "action_type": "watchlist",
  "is_active": false
}
```

Response `200`:

```json
{
  "performance_id": "PF123456",
  "action_type": "interest",
  "is_active": true,
  "is_interested": true,
  "is_watchlisted": false,
  "zzim_count": 1
}
```

DB에는 `true/false` 텍스트를 저장하지 않습니다.  
`users_performance_actions` 테이블에 해당 row가 있으면 활성 상태, 없으면 비활성 상태입니다.

## 로그 API

로그 API는 인증 없이도 호출할 수 있습니다.  
다만 인증 헤더가 있으면 해당 사용자 로그로 저장되고, 없으면 익명 로그로 저장됩니다.

공연 목록 검색과 공연 상세 조회는 백엔드에서 자동으로 로그를 저장합니다.  
프론트에서 별도 이벤트를 기록하고 싶을 때 아래 API를 사용합니다.

### 검색 로그 저장

```http
POST {{base_url}}/logs/search/
```

Request:

```json
{
  "keyword": "햄릿",
  "filter_region": "seoul",
  "filter_genre": "play",
  "filter_status": "performing"
}
```

Response `201`:

```json
{
  "id": 1,
  "keyword": "햄릿",
  "filter_region": "seoul",
  "filter_genre": "play",
  "filter_status": "performing",
  "created_at": "2026-06-09T00:00:00+09:00"
}
```

### 조회/행동 로그 저장

```http
POST {{base_url}}/logs/view/
```

Request:

```json
{
  "performance_id": "PF123456",
  "log_type": "detail"
}
```

`log_type` 예시:

```text
detail
interest_on
interest_off
watchlist_on
watchlist_off
```

Response `201`:

```json
{
  "id": 1,
  "performance_id": "PF123456",
  "log_type": "detail",
  "created_at": "2026-06-09T00:00:00+09:00"
}
```

### QnA/AI 추천 로그 저장

```http
POST {{base_url}}/logs/qna/
```

Request:

```json
{
  "question": "이번 주말에 볼 수 있는 뮤지컬 추천해줘",
  "answer": "추천 결과 텍스트"
}
```

Response `201`:

```json
{
  "id": 1,
  "question": "이번 주말에 볼 수 있는 뮤지컬 추천해줘",
  "answer": "추천 결과 텍스트",
  "created_at": "2026-06-09T00:00:00+09:00"
}
```

## 로컬 데이터 적재

프론트 연동 검증용 샘플 fixture가 준비되어 있습니다.  
샘플은 크지 않지만 목록/검색/필터/상세/관심 토글 테스트가 가능하도록 구성되어 있습니다.

샘플 구성:

```text
공연장 8개
공연 12개
상세 이미지 12개
예매 링크 12개
```

적재 순서:

```bash
python manage.py loaddata fixtures/venues_sample.json
python manage.py loaddata fixtures/performances_sample.json
python manage.py loaddata fixtures/performance_images_sample.json
python manage.py loaddata fixtures/booking_links_sample.json
```

샘플 데이터로 검증 가능한 항목:

```text
장르 필터: 연극, 뮤지컬, 클래식, 국악, 대중음악, 무용, 복합, 서커스/마술
지역 필터: 서울, 경기, 부산, 대구, 광주, 대전, 제주
상태 필터: 공연예정, 공연중, 공연완료
상세 조회: synopsis, images, booking_links 포함
부가 필드: 가격, 무료 여부, 어린이 공연, 축제 여부
```

샘플 검색어:

```text
햄릿
레미제라블
헬로카봇
재즈
제주
```

샘플 공연 ID:

```text
PF900001  햄릿
PF900002  레미제라블
PF900003  헬로카봇 스페셜: 전설의 용사를 찾아서
PF900010  제주 인디 콘서트
```

샘플은 프론트 연동 확인용 고정 데이터입니다.  
기존 KOPIS 데이터가 많은 DB에 섞어 넣기보다는, 프론트 연동용 개발 DB나 비어 있는 DB에서 사용하는 것을 권장합니다.
실제 KOPIS 데이터 기반 검색 품질이나 추천 후보 품질을 확인하려면 아래 동기화 명령을 사용합니다.

KOPIS 동기화:

```bash
python manage.py sync_kopis --with-venues --stdate 20260101 --eddate 20261231
```

뮤지컬만 빠르게 적재:

```bash
python manage.py sync_kopis --with-venues --genre GGGA --stdate 20260101 --eddate 20261231
```

## 프론트 연동 체크리스트

- 로그인 성공 시 `access`, `refresh`를 저장합니다.
- 인증 API 호출 시 `Authorization: Bearer {access}` 헤더를 붙입니다.
- 토큰 재발급 응답에 새 `refresh`가 오면 기존 refresh token을 교체합니다.
- 소셜 로그인 callback route는 아래 패턴으로 통일합니다.

```text
/auth/callback/google
/auth/callback/naver
```

- Google/Naver 개발자 콘솔의 redirect URI와 프론트에서 전달하는 `redirect_uri` 값은 완전히 같아야 합니다.
- 공연 목록은 `searchData`를 사용합니다.
- 상세 페이지는 로그인 상태라면 인증 헤더를 붙여 `is_interested`, `is_watchlisted`를 사용자 기준으로 받습니다.
- 관심/볼예정 버튼은 `POST /performances/{id}/actions/` 하나를 사용하고 `action_type`만 바꿉니다.
