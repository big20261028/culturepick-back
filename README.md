# CulturePick Backend

공연예술통합전산망(KOPIS) 데이터를 기반으로 공연 검색, 공연 상세, 관심/볼예정, 사용자 로그, OpenAI 추천 기능을 제공하는 Django REST API 서버입니다.

이 문서는 프론트엔드에서 API를 연동할 때 필요한 정보를 우선으로 정리합니다.

---

## 현재 배포 상태

| 항목 | 값 |
|---|---|
| 운영 서버 | Elastic Beanstalk |
| 운영 DB | AWS RDS PostgreSQL |
| 운영 Base URL | `http://culturepick.ap-northeast-2.elasticbeanstalk.com` |
| API Prefix | `/api/v1` |
| Health Check | `GET /health/` |
| 인증 방식 | JWT Bearer Token |

Health check:

```http
GET http://culturepick.ap-northeast-2.elasticbeanstalk.com/health/
```

정상 응답:

```json
{"status": "ok"}
```

프론트에서는 환경변수 예시를 아래처럼 둘 수 있습니다.

```env
VITE_API_BASE_URL=http://culturepick.ap-northeast-2.elasticbeanstalk.com
```

---

## 인증 공통 규칙

로그인 후 받은 access token을 인증이 필요한 API에 전달합니다.

```http
Authorization: Bearer <access_token>
Content-Type: application/json
```

인증이 필요한 주요 API:

- 로그아웃
- 관심/볼예정 토글
- OpenAI 추천 요청
- 추천 피드백 저장

공연 목록/상세/검색은 비로그인도 호출 가능합니다. 단, 로그인 상태에서 호출하면 응답의 `is_interested`, `is_watchlisted`가 현재 사용자 기준으로 내려옵니다.

---

## 빠른 연동 순서

1. `GET /health/`로 서버 상태 확인
2. `POST /api/v1/auth/register/` 회원가입
3. `POST /api/v1/auth/login/` 로그인 후 토큰 저장
4. `GET /api/v1/performances/` 공연 목록 확인
5. `GET /api/v1/performances/?keyword=...` 통합검색 확인
6. `GET /api/v1/performances/{performance_id}/` 상세 확인
7. `POST /api/v1/performances/{performance_id}/actions/` 관심/볼예정 토글 확인
8. `POST /api/v1/recommendations/ai/` OpenAI 추천 확인
9. `POST /api/v1/recommendations/{session_id}/feedback/` 추천 피드백 저장 확인

---

## Auth API

### 회원가입

```http
POST /api/v1/auth/register/
```

Request:

```json
{
  "email": "user@example.com",
  "password": "ValidPass123!",
  "password_confirm": "ValidPass123!",
  "nickname": "문화러"
}
```

Response `201`:

```json
{
  "message": "회원가입이 완료되었습니다."
}
```

회원가입 검증 조건:

- 이메일은 공백 제거 후 검사합니다.
- 이메일은 필수이며 `@`를 포함해야 합니다.
- 이메일에는 이모티콘을 사용할 수 없습니다.
- 이메일 형식은 `^[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}$` 기준입니다.
- 비밀번호는 8자 이상이어야 합니다.
- 비밀번호에는 영문자, 숫자, 특수문자 `!@#$%^&*(),.?":{}|<>`가 각각 1개 이상 포함되어야 합니다.
- 비밀번호와 비밀번호 확인 값이 일치해야 합니다.

### 로그인

```http
POST /api/v1/auth/login/
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
  "access": "<jwt_access_token>",
  "refresh": "<jwt_refresh_token>"
}
```

### 토큰 갱신

```http
POST /api/v1/auth/token/refresh/
```

Request:

```json
{
  "refresh": "<jwt_refresh_token>"
}
```

Response:

```json
{
  "access": "<new_access_token>",
  "refresh": "<new_refresh_token>"
}
```

### 로그아웃

```http
POST /api/v1/auth/logout/
Authorization: Bearer <access_token>
```

Request:

```json
{
  "refresh": "<jwt_refresh_token>"
}
```

### 소셜 로그인

```http
POST /api/v1/auth/social/
```

Request:

```json
{
  "provider": "google",
  "code": "<authorization_code>",
  "redirect_uri": "http://localhost:5173/auth/callback/google"
}
```

`provider`는 `google`, `naver`, `kakao`를 받을 수 있습니다. 네이버는 필요 시 `state`도 함께 전달합니다.

```json
{
  "provider": "naver",
  "code": "<authorization_code>",
  "state": "<state>",
  "redirect_uri": "http://localhost:5173/auth/callback/naver"
}
```

---

## My Page API

마이페이지의 관심 공연과 볼 예정 공연은 로그인 사용자의 `UsersPerformanceAction` 데이터를 조회해서 내려줍니다. 응답의 `results`는 공연 목록 API와 같은 공연 카드 구조이므로 기존 공연 카드 컴포넌트를 재사용할 수 있습니다.

### 내 회원정보 조회

```http
GET /api/v1/auth/me/
Authorization: Bearer <access_token>
```

Response:

```json
{
  "email": "user@example.com",
  "nickname": "문화러",
  "display_name": "문화러",
  "phone": "010-1234-5678",
  "provider": "local",
  "created_at": "2026-06-22T12:00:00+09:00",
  "updated_at": "2026-06-22T12:00:00+09:00",
  "can_change_password": true,
  "requires_password_verification": true
}
```

소셜 로그인 계정은 로컬 비밀번호가 없으므로 `can_change_password=false`, `requires_password_verification=false`로 내려갑니다.
`display_name`은 `nickname`이 있으면 닉네임, 없으면 이메일로 내려갑니다. 프론트에서 사용자명을 표기할 때는 이 필드를 사용하면 됩니다.

### 회원정보 수정 전 비밀번호 확인

```http
POST /api/v1/auth/me/password/verify/
Authorization: Bearer <access_token>
```

Request:

```json
{
  "password": "ValidPass123!"
}
```

Response:

```json
{
  "verified": true,
  "verification_token": "<profile_update_token>",
  "expires_in": 600
}
```

`verification_token`은 10분 동안 유효합니다. 프론트는 이 토큰을 회원 수정 페이지로 전달하거나 상태에 보관한 뒤, 실제 수정 요청에 포함해야 합니다.

소셜 로그인 계정은 이 API를 사용할 수 없습니다. 소셜 로그인 계정의 기본 프로필 수정은 `PATCH /api/v1/auth/me/`를 바로 호출하면 됩니다.

### 내 회원정보 수정

```http
PATCH /api/v1/auth/me/
Authorization: Bearer <access_token>
```

Request:

```json
{
  "verification_token": "<profile_update_token>",
  "nickname": "새 닉네임",
  "phone": "010-9999-9999",
  "new_password": "NewValidPass123!",
  "new_password_confirm": "NewValidPass123!"
}
```

수정할 필드만 보내면 됩니다. 비밀번호를 바꾸지 않을 때는 `new_password`, `new_password_confirm`을 생략하거나 둘 다 빈 문자열로 보내면 됩니다.

로컬 계정은 `verification_token`이 필요합니다. 소셜 로그인 계정은 `verification_token` 없이 `nickname`, `phone`을 수정할 수 있지만, 이 API에서 비밀번호 변경은 지원하지 않습니다.

수정 가능 필드:

- `nickname`
- `phone`
- `new_password`, `new_password_confirm`

읽기 전용 필드:

- `email`
- `provider`
- `created_at`
- `updated_at`

### 관심 공연 목록

```http
GET /api/v1/auth/me/interests/
Authorization: Bearer <access_token>
```

Response:

```json
{
  "type": "interest",
  "total": 1,
  "results": [
    {
      "performance_id": "PF000001",
      "title": "공연 제목",
      "genre": "뮤지컬",
      "genre_code": "GGGA",
      "poster_url": "https://...",
      "venue": {
        "venue_id": "FC000001",
        "name": "공연장명",
        "sido": "서울특별시",
        "gugun": "종로구"
      },
      "is_interested": true,
      "is_watchlisted": false,
      "search_score": 0
    }
  ]
}
```

### 볼 예정 공연 목록

```http
GET /api/v1/auth/me/watchlist/
Authorization: Bearer <access_token>
```

Response:

```json
{
  "type": "watchlist",
  "total": 1,
  "results": [
    {
      "performance_id": "PF000002",
      "title": "볼 예정 공연",
      "genre": "연극",
      "genre_code": "AAAA",
      "poster_url": "https://...",
      "venue": {
        "venue_id": "FC000002",
        "name": "공연장명",
        "sido": "부산광역시",
        "gugun": "해운대구"
      },
      "is_interested": false,
      "is_watchlisted": true,
      "search_score": 0
    }
  ]
}
```

---

## Performances API

### 공연 목록/통합검색/상세검색

```http
GET /api/v1/performances/
```

Query parameters:

| 이름 | 설명 | 예시 |
|---|---|---|
| `keyword` | 공연명, 출연진, 공연장 통합검색 | `레미제라블` |
| `genre` | 장르 필터 | `musical`, `GGGA` |
| `local` | 지역 필터 | `seoul`, `busan`, `세종특별자치시` |
| `region` | `local`과 동일한 지역 필터 alias | `seoul` |
| `status` | 공연 상태 | `upcoming`, `performing`, `done` |
| `pageNum` | 페이지 번호 | `1` |
| `page` | `pageNum` alias | `1` |
| `pageSize` | 페이지 크기 | `20` |
| `page_size` | `pageSize` alias | `20` |
| `sorted` | 정렬 | `latest`, `popular`, `views`, `zzim`, `title`, `date` |
| `sort` | `sorted` alias | `latest` |

예시:

```http
GET /api/v1/performances/?keyword=뮤지컬&genre=musical&local=seoul&pageNum=1&pageSize=20&sorted=latest
```

Response:

```json
{
  "pageNum": 1,
  "pageSize": 20,
  "total": 1,
  "searchData": [
    {
      "performance_id": "PF000001",
      "title": "공연 제목",
      "genre": "뮤지컬",
      "genre_code": "GGGA",
      "start_date": "2026-06-01",
      "end_date": "2026-06-30",
      "status": "공연중",
      "status_code": "02",
      "poster_url": "https://...",
      "runtime": "150분",
      "age_rating": "8세 이상",
      "min_price": 50000,
      "max_price": 150000,
      "is_free": false,
      "price_options": [
        {
          "label": "R석",
          "price": 150000,
          "currency": "KRW",
          "raw_text": "R석 150,000원",
          "sort_order": 0
        },
        {
          "label": "S석",
          "price": 100000,
          "currency": "KRW",
          "raw_text": "S석 100,000원",
          "sort_order": 1
        }
      ],
      "openrun": false,
      "is_child": false,
      "is_festival": false,
      "venue": {
        "venue_id": "FC000001",
        "name": "공연장명",
        "sido": "서울특별시",
        "gugun": "종로구",
        "address": "서울특별시 종로구 ...",
        "latitude": "37.1234567",
        "longitude": "127.1234567"
      },
      "view_count": 0,
      "zzim_count": 0,
      "is_interested": false,
      "is_watchlisted": false,
      "search_score": 0
    }
  ],
  "page": 1,
  "page_size": 20,
  "results": [
    {
      "performance_id": "PF000001",
      "title": "공연 제목",
      "genre": "뮤지컬",
      "genre_code": "GGGA",
      "start_date": "2026-06-01",
      "end_date": "2026-06-30",
      "status": "공연중",
      "status_code": "02",
      "poster_url": "https://...",
      "runtime": "150분",
      "age_rating": "8세 이상",
      "min_price": 50000,
      "max_price": 150000,
      "is_free": false,
      "price_options": [
        {
          "label": "R석",
          "price": 150000,
          "currency": "KRW",
          "raw_text": "R석 150,000원",
          "sort_order": 0
        },
        {
          "label": "S석",
          "price": 100000,
          "currency": "KRW",
          "raw_text": "S석 100,000원",
          "sort_order": 1
        }
      ],
      "openrun": false,
      "is_child": false,
      "is_festival": false,
      "venue": {
        "venue_id": "FC000001",
        "name": "공연장명",
        "sido": "서울특별시",
        "gugun": "종로구",
        "address": "서울특별시 종로구 ...",
        "latitude": "37.1234567",
        "longitude": "127.1234567"
      },
      "view_count": 0,
      "zzim_count": 0,
      "is_interested": false,
      "is_watchlisted": false,
      "search_score": 0
    }
  ]
}
```

`searchData`와 `results`는 프론트 호환을 위해 함께 내려갑니다. 신규 연동에서는 `searchData` 기준 사용을 권장합니다.

### 지역 필터 참고

프론트 alias:

| alias | 포함 지역 |
|---|---|
| `seoul` | 서울 |
| `gyeonggi` | 경기, 인천 |
| `chungcheong` | 충청, 강원, 대전, 세종 |
| `daegu` | 대구, 경북 |
| `busan` | 부산, 경남, 울산 |
| `gwangju` | 광주, 전라 |
| `jeju` | 제주, 기타, 미분류, 해외 |

현재 데이터 정책:

- 국내 일반 주소: `sido`, `gugun` 모두 저장
- 세종특별자치시: `sido="세종특별자치시"`, `gugun=""`
- 해외 공연장: `sido=""`, `gugun=""` 허용
- `경기도 성남시 분당구 ...` 같은 주소는 `sido="경기도"`, `gugun="성남시"`로 저장

### 공연 상세

```http
GET /api/v1/performances/{performance_id}/
```

상세 응답에는 목록 필드에 더해 `synopsis`, `schedule_info`, `images`, `booking_links`, 제작/기획 정보 등이 포함됩니다.

응답 일부:

```json
{
  "performance_id": "PF000001",
  "title": "공연 제목",
  "synopsis": "공연 소개",
  "schedule_info": "화~금 20:00",
  "venue": {
    "venue_id": "FC000001",
    "name": "공연장명",
    "sido": "서울특별시",
    "gugun": "종로구",
    "address": "서울특별시 종로구 ..."
  },
  "images": [
    {
      "image_url": "https://...",
      "sort_order": 0
    }
  ],
  "booking_links": [
    {
      "site_name": "예매처",
      "url": "https://..."
    }
  ],
  "is_interested": false,
  "is_watchlisted": false
}
```

### 관심/볼예정 토글

```http
POST /api/v1/performances/{performance_id}/actions/
Authorization: Bearer <access_token>
```

Request:

```json
{
  "action_type": "interest"
}
```

또는 명시적으로 켜고 끄기:

```json
{
  "action_type": "watchlist",
  "is_active": true
}
```

`action_type`:

- `interest`: 관심 등록
- `watchlist`: 볼예정 등록

Response:

```json
{
  "performance_id": "PF000001",
  "action_type": "interest",
  "is_active": true,
  "is_interested": true,
  "is_watchlisted": false,
  "zzim_count": 12
}
```

---

## Community API

자유게시판 기능입니다. Tiptap/Toast UI Editor가 만든 본문을 `content`에 저장하고, 프론트는 `content_format`으로 렌더링 방식을 구분하면 됩니다.

지원 포맷:

- `html`: Tiptap HTML 또는 Toast 렌더링 HTML
- `markdown`: Toast UI Markdown
- `json`: Tiptap/ProseMirror JSON 문자열

HTML을 렌더링할 때는 프론트에서 DOMPurify 같은 sanitizer를 반드시 적용하세요.

### 게시글 목록

```http
GET /api/v1/community/posts/
```

Query parameters:

| 이름 | 설명 | 예시 |
|---|---|---|
| `keyword` | 제목 검색 | `후기` |
| `page` | 페이지 번호 | `1` |
| `page_size` | 페이지 크기 | `20` |

Response:

```json
{
  "total": 1,
  "page": 1,
  "page_size": 20,
  "results": [
    {
      "id": 1,
      "author": 3,
      "author_email": "user@example.com",
      "author_nickname": "문화러",
      "author_display_name": "문화러",
      "title": "공연 후기",
      "content": "<p>좋았어요.</p>",
      "content_format": "html",
      "thumbnail_url": "https://...",
      "view_count": 0,
      "comment_count": 2,
      "created_at": "2026-06-22T12:00:00+09:00",
      "updated_at": "2026-06-22T12:00:00+09:00"
    }
  ]
}
```

게시글/댓글 작성자 표기는 `author_display_name`을 사용합니다. 작성자 닉네임이 없으면 이메일이 들어갑니다.

### 게시글 작성

```http
POST /api/v1/community/posts/
Authorization: Bearer <access_token>
```

Request:

```json
{
  "title": "공연 후기",
  "content": "<p>이미지와 함께 남기는 후기입니다.</p>",
  "content_format": "html",
  "thumbnail_url": "https://culturepick-community-images-241732001230-ap-northeast-2-an.s3.ap-northeast-2.amazonaws.com/community/images/..."
}
```

### 게시글 상세/수정/삭제

```http
GET /api/v1/community/posts/{id}/
PATCH /api/v1/community/posts/{id}/
DELETE /api/v1/community/posts/{id}/
```

수정/삭제는 작성자만 가능합니다.

### 댓글 목록/작성

```http
GET /api/v1/community/posts/{post_id}/comments/
POST /api/v1/community/posts/{post_id}/comments/
```

댓글 작성은 로그인이 필요합니다.

Request:

```json
{
  "content": "댓글 내용입니다."
}
```

### 댓글 수정/삭제

```http
PATCH /api/v1/community/comments/{id}/
DELETE /api/v1/community/comments/{id}/
```

수정/삭제는 작성자만 가능합니다.

### 에디터 이미지 업로드

```http
POST /api/v1/community/images/
Authorization: Bearer <access_token>
Content-Type: multipart/form-data
```

Form data:

```text
image=<file>
```

허용 타입:

- `image/jpeg`
- `image/png`
- `image/webp`
- `image/gif`

최대 크기: 5MB

Response:

```json
{
  "id": 1,
  "image": "community/images/2026/06/22/....png",
  "image_url": "https://culturepick-community-images-241732001230-ap-northeast-2-an.s3.ap-northeast-2.amazonaws.com/community/images/2026/06/22/....png",
  "original_name": "poster.png",
  "size": 12345,
  "content_type": "image/png",
  "created_at": "2026-06-22T12:00:00+09:00"
}
```

프론트 에디터 연동 흐름:

1. 에디터에서 이미지 삽입 이벤트 발생
2. `/api/v1/community/images/`에 multipart 업로드
3. 응답의 `image_url`을 에디터 본문에 삽입
4. 게시글 작성 시 `content` 안에 이미지 URL이 포함된 상태로 저장

---

## Recommendations API

추천 API는 두 단계로 나뉩니다.

- 후보 조회: OpenAI 호출 없이 백엔드 추천 후보만 조회
- AI 추천: 후보를 OpenAI에 전달해 친근한 추천 이유와 순위를 생성

### 추천 후보 조회

```http
POST /api/v1/recommendations/candidates/
```

비로그인도 호출 가능하지만, 로그인 상태에서 호출하면 사용자 로그/관심/볼예정 정보가 반영됩니다.

Request:

```json
{
  "message": "이번 주말에 볼만한 뮤지컬 추천해줘",
  "limit": 20
}
```

Response:

```json
{
  "message": "이번 주말에 볼만한 뮤지컬 추천해줘",
  "profile": {
    "vector": {},
    "source_summary": {}
  },
  "total": 20,
  "candidates": [
    {
      "performance": {
        "performance_id": "PF000001",
        "title": "공연 제목",
        "genre": "뮤지컬",
        "venue": {
          "sido": "서울특별시",
          "gugun": "종로구"
        }
      },
      "score": 8.3,
      "reasons": ["선호 장르와 유사한 공연입니다."],
      "contributions": []
    }
  ]
}
```

### OpenAI 추천

```http
POST /api/v1/recommendations/ai/
Authorization: Bearer <access_token>
```

Request:

```json
{
  "message": "이번 주말에 친구랑 볼만한 뮤지컬 추천해줘",
  "limit": 5,
  "candidate_limit": 30,
  "include_candidates": false
}
```

필드:

| 이름 | 설명 | 기본값 |
|---|---|---|
| `message` | 사용자 요청 문장 | `""` |
| `prompt` | `message` alias | `""` |
| `limit` | 최종 추천 개수, 1~10 | `5` |
| `candidate_limit` | OpenAI에 전달할 후보 수, 5~50 | `30` |
| `include_candidates` | 디버그용 후보/프로필 포함 여부 | `false` |

Response:

```json
{
  "session_id": 12,
  "summary": "친구와 보기 좋은 분위기의 뮤지컬 위주로 골라봤어요.",
  "message": "친구와 보기 좋은 분위기의 뮤지컬 위주로 골라봤어요.",
  "fallback_used": false,
  "validation_status": "passed",
  "recommendations": [
    {
      "performance_id": "PF000001",
      "title": "공연 제목",
      "reason": "최근 관심을 보인 뮤지컬 장르와 잘 맞고, 접근성도 좋은 공연이에요.",
      "rank": 1,
      "source": "openai",
      "score": 9.1
    }
  ],
  "results": [
    {
      "id": 1,
      "rank": 1,
      "score": 9.1,
      "reason": "최근 관심을 보인 뮤지컬 장르와 잘 맞고, 접근성도 좋은 공연이에요.",
      "source": "openai",
      "performance": {
        "performance_id": "PF000001",
        "title": "공연 제목",
        "venue": {
          "sido": "서울특별시",
          "gugun": "종로구"
        }
      }
    }
  ]
}
```

`recommendations`는 프론트 표시용으로 가볍게 가공된 배열이고, `results`는 공연 카드 렌더링에 필요한 상세 정보가 포함된 배열입니다.

### 추천 피드백 저장

```http
POST /api/v1/recommendations/{session_id}/feedback/
Authorization: Bearer <access_token>
```

Request:

```json
{
  "performance_id": "PF000001",
  "feedback_type": "interest",
  "metadata": {
    "source": "recommendation_card"
  }
}
```

`feedback_type`:

| 값 | 의미 | 학습 신호 |
|---|---|---|
| `click` | 상세 클릭 | 약한 긍정 |
| `interest` | 관심 등록 | 중간 긍정 |
| `watchlist` | 볼예정 등록 | 강한 긍정 |
| `booking_link` | 예매 링크 클릭 | 최상위 긍정 |
| `thumbs_up` | 좋아요 | 긍정 |
| `thumbs_down` | 싫어요 | 강한 부정 |
| `regenerate` | 재추천 요청 | 중간 부정 |
| `reason_not_helpful` | 추천 이유가 도움 안 됨 | 강한 부정 |
| `not_my_taste` | 취향 아님 | 부정 |
| `already_seen` | 이미 본 공연 | 약한 부정/제외 신호 |

주의:

- `session_id`는 해당 사용자의 추천 세션이어야 합니다.
- `performance_id`를 전달하는 경우 해당 추천 세션에 포함된 공연이어야 합니다.
- 피드백은 추후 파인튜닝/품질 평가 후보 데이터 생성에 사용됩니다.

---

## Logs API

공연 목록/상세/액션 일부는 백엔드에서 자동 로그를 남깁니다. 프론트에서 별도 이벤트를 남기고 싶을 때 아래 API를 사용할 수 있습니다.

### 검색 로그

```http
POST /api/v1/logs/search/
```

```json
{
  "keyword": "뮤지컬",
  "filter_region": "seoul",
  "filter_genre": "musical",
  "filter_status": "performing"
}
```

### 조회/행동 로그

```http
POST /api/v1/logs/view/
```

```json
{
  "performance_id": "PF000001",
  "log_type": "detail"
}
```

### QnA/AI 로그

```http
POST /api/v1/logs/qna/
```

```json
{
  "question": "이번 주말 볼만한 공연 추천해줘",
  "answer": "친구와 보기 좋은 뮤지컬을 추천드릴게요."
}
```

로그 API는 비로그인도 호출 가능하지만, 로그인 상태에서 `Authorization` 헤더를 전달하면 사용자와 연결됩니다.

---

## 프론트 연동 체크리스트

### 필수

- 운영 Base URL이 `http://culturepick.ap-northeast-2.elasticbeanstalk.com`인지 확인
- 로그인 후 access token을 `Authorization: Bearer ...`로 전달
- access token 만료 시 `POST /api/v1/auth/token/refresh/` 호출
- 공연 목록은 `searchData` 기준으로 렌더링
- 공연 상세 진입 시 `performance_id` 사용
- 관심/볼예정 버튼은 `is_interested`, `is_watchlisted` 응답값으로 상태 갱신
- 게시판 본문 HTML 렌더링 시 DOMPurify 등으로 sanitize
- 에디터 이미지는 먼저 `/api/v1/community/images/`에 업로드한 뒤 응답 `image_url`을 본문에 삽입
- 추천 API는 로그인 필요
- 추천 피드백 저장 시 `session_id` 보관 필요

### CORS/CSRF

프론트 배포 도메인이 정해지면 백엔드 Elastic Beanstalk 환경변수에 추가해야 합니다.

```env
CORS_ALLOWED_ORIGINS=https://your-frontend-domain.com
CSRF_TRUSTED_ORIGINS=https://your-frontend-domain.com
```

로컬 프론트에서 운영 백엔드를 직접 호출해야 한다면 임시로 아래 origin도 추가할 수 있습니다.

```env
CORS_ALLOWED_ORIGINS=http://localhost:5173
CSRF_TRUSTED_ORIGINS=http://localhost:5173
```

여러 값은 쉼표로 구분합니다.

```env
CORS_ALLOWED_ORIGINS=https://culturepick.com,http://localhost:5173
```

---

## KOPIS 데이터 적재

AWS 1차 배포에서는 Redis/Celery 자동 수집을 제외했습니다. 공연 데이터는 수동 management command로 적재합니다.

### 수동 적재

```bash
python manage.py sync_kopis --stdate 20260601 --eddate 20260630 --genre GGGA --with-venues
```

장르 코드:

| 코드 | 장르 |
|---|---|
| `AAAA` | 연극 |
| `GGGA` | 뮤지컬 |
| `CCCA` | 클래식 |
| `CCCC` | 국악 |
| `CCCD` | 대중음악 |
| `BBBC` | 무용 |

`sync_kopis`는 venue 생성/갱신 시 주소를 기반으로 `sido`, `gugun`을 자동 저장합니다.

### 기존 venue 지역 보정

기존 데이터의 `sido/gugun`을 보정할 때 사용합니다.

```bash
python manage.py fill_venue_region
```

기본은 빈 값/이상값만 채웁니다. 모든 venue를 주소 기준으로 다시 계산하려면 명시적으로 `--overwrite`를 붙입니다.

```bash
python manage.py fill_venue_region --overwrite
```

---

## AWS 운영 명령 참고

Elastic Beanstalk EC2에 접속한 뒤 실행 중인 컨테이너를 확인합니다.

```bash
sudo docker ps
```

컨테이너 안에서 Django 명령을 실행합니다.

```bash
sudo docker exec -it <container_id> python manage.py sync_kopis --stdate 20260601 --eddate 20260630 --genre GGGA --with-venues
```

데이터 개수 확인:

```bash
sudo docker exec -it <container_id> python manage.py shell -c "from apps.performances.models import Performance, Venue; print('performances=', Performance.objects.count(), 'venues=', Venue.objects.count())"
```

---

## 로컬 개발

### 요구사항

- Python 3.12 권장
- Docker Desktop
- PostgreSQL/Redis는 `docker-compose.local.yml` 사용

### 설치

```bash
git clone https://github.com/big20261028/culturepick-back.git
cd culturepick-back
python -m venv .venv
```

Git Bash:

```bash
source .venv/Scripts/activate
```

PowerShell:

```powershell
.\.venv\Scripts\Activate.ps1
```

패키지 설치:

```bash
pip install -r requirements/local.txt
```

환경변수 파일:

```bash
cp .env.example .env
```

로컬 DB/Redis 실행:

```bash
docker compose -f docker-compose.local.yml up -d db redis
```

마이그레이션:

```bash
python manage.py migrate
```

서버 실행:

```bash
python manage.py runserver
```

로컬 서버:

```text
http://127.0.0.1:8000
```

---

## AWS 배포

현재 배포용 루트 `docker-compose.yml`은 web, celery-worker, celery-beat 컨테이너를 기본 실행합니다.

- Django settings: `BE.settings.production`
- 실행 서버: `gunicorn` (`--workers 1`)
- DB: RDS PostgreSQL
- Redis/Celery: celery-worker는 `--concurrency=1`로 실행하며, celery-beat는 PostgreSQL RDS와 ElastiCache Valkey Serverless를 사용합니다.

배포 zip 생성 예시:

```powershell
tar -a -cf culturepick-backend-eb.zip --exclude='__pycache__' --exclude='*.pyc' Dockerfile docker-compose.yml manage.py requirements BE apps common docker .platform .ebignore
```

web 컨테이너는 `gunicorn` 시작 전에 `python manage.py migrate --noinput`을 자동 실행합니다. 새 모델이나 migration이 추가된 경우에도 별도 SSH 접속 없이 배포 과정에서 DB 스키마가 갱신됩니다.

배포 로그에서 아래 메시지를 확인하면 migration이 정상 실행된 것입니다.

```text
Running database migrations...
Operations to perform:
```

Elastic Beanstalk 필수 환경변수:

```env
DJANGO_SECRET_KEY=your-production-secret
DJANGO_DEBUG=False
DJANGO_ALLOWED_HOSTS=culturepick.ap-northeast-2.elasticbeanstalk.com
DJANGO_SETTINGS_MODULE=BE.settings.production

DATABASE_URL=postgresql://USER:PASSWORD@RDS_ENDPOINT:5432/culturepick

KOPIS_API_KEY=your-kopis-api-key
OPENAI_API_SECRET_KEY=your-openai-key
OPENAI_RECOMMENDATION_MODEL=gpt-4o-mini

REDIS_URL=rediss://your-elasticache-serverless-endpoint:6379/0
CELERY_BROKER_URL=rediss://your-elasticache-serverless-endpoint:6379/0
CELERY_RESULT_BACKEND=django-db
CELERY_ENABLE_KOPIS_BEAT_SCHEDULE=False
CELERY_WORKER_ENABLE_REMOTE_CONTROL=False
CELERY_REDIS_GLOBAL_KEYPREFIX={culturepick-celery}:
CELERY_REDIS_RESULT_GLOBAL_KEYPREFIX={culturepick-celery-result}:

AWS_STORAGE_BUCKET_NAME=culturepick-community-images-241732001230-ap-northeast-2-an
AWS_S3_REGION_NAME=ap-northeast-2
AWS_S3_CUSTOM_DOMAIN=culturepick-community-images-241732001230-ap-northeast-2-an.s3.ap-northeast-2.amazonaws.com

CORS_ALLOWED_ORIGINS=https://your-frontend-domain.com
CSRF_TRUSTED_ORIGINS=https://your-frontend-domain.com

DJANGO_SECURE_SSL_REDIRECT=False
DJANGO_SESSION_COOKIE_SECURE=False
DJANGO_CSRF_COOKIE_SECURE=False
DJANGO_SECURE_HSTS_SECONDS=0
```

`DATABASE_URL` 대신 아래 `DB_*` 환경변수도 사용할 수 있습니다.

```env
DB_NAME=culturepick
DB_USER=your-rds-username
DB_PASSWORD=your-rds-password
DB_HOST=your-rds-endpoint
DB_PORT=5432
```

Redis/Celery 환경변수를 Elastic Beanstalk에 추가하거나 수정한 뒤에는 이미 실행 중인 컨테이너에 즉시 반영되지 않을 수 있습니다. EB 콘솔에서 앱 서버를 다시 시작하거나 새 zip을 재배포한 뒤 컨테이너 안에서 값을 확인합니다.

```bash
sudo docker exec -it current-web-1 sh
printenv | grep -E "REDIS|CELERY|DJANGO"
```

EC2 host에는 값이 있는데 컨테이너 안에 없다면, `docker-compose.yml`의 `services.web.environment`에 해당 변수가 명시되어 있는지 확인합니다.

```bash
sudo /opt/elasticbeanstalk/bin/get-config environment | grep -E "REDIS|CELERY"
```

배포 후에는 컨테이너가 3개 떠 있는지 확인합니다.

```bash
sudo docker ps
```

기대 컨테이너:

```text
current-web-1
current-celery-worker-1
current-celery-beat-1
```

worker/beat 로그 확인:

```bash
sudo docker logs -f current-celery-worker-1
sudo docker logs -f current-celery-beat-1
```

ElastiCache Valkey Serverless는 클러스터형 Redis처럼 동작하므로 Celery의 remote control, mingle, gossip 기능이 여러 Redis key를 동시에 조회하다가 아래 오류를 낼 수 있습니다.

```text
CROSSSLOT Keys in request don't hash to the same slot
```

현재 배포 설정은 이를 피하기 위해 worker를 `--without-mingle --without-gossip`로 실행하고, `CELERY_WORKER_ENABLE_REMOTE_CONTROL=False`를 기본값으로 사용합니다. Redis key도 같은 hash slot에 들어가도록 `CELERY_REDIS_GLOBAL_KEYPREFIX`에 `{culturepick-celery}:` 형태의 hash tag prefix를 사용합니다.

micro급 인스턴스에서는 Docker, Django, Gunicorn, Celery를 함께 실행하면 메모리 사용률이 높아질 수 있습니다. 현재 배포 설정은 비용을 우선해 Gunicorn worker를 1개로, Celery worker concurrency를 1로 제한합니다. 이 상태에서도 메모리 경고가 계속되면 `t3.small` 이상으로 올리거나 celery-beat 분리를 검토합니다.

Celery 연결 테스트:

```bash
sudo docker exec -it current-web-1 sh
python manage.py shell
```

```python
from apps.performances.tasks import ping_task

result = ping_task.delay()
result.id
```

worker 로그에 `apps.performances.tasks.ping_task` 수신/성공 로그가 보이면 정상입니다.

KOPIS 동기화 task는 처음부터 긴 기간으로 실행하지 말고 짧은 기간/단일 장르로 테스트합니다.

```python
from apps.performances.tasks import sync_kopis_task

sync_kopis_task.delay(
    stdate="20260701",
    eddate="20260702",
    genre="CCCA",
    with_venues=True,
)
```

자동 KOPIS 주기 수집은 worker/beat와 수동 task 검증이 끝난 뒤 켭니다.

```env
CELERY_ENABLE_KOPIS_BEAT_SCHEDULE=True
```

이 값을 켜면 `sync_ongoing_performances`, `sync_upcoming_performances` beat schedule이 활성화됩니다.

현재 `docker-compose.yml`에는 PostgreSQL/Redis 컨테이너를 포함하지 않습니다. PostgreSQL은 RDS, Redis는 ElastiCache Valkey Serverless를 사용합니다.

주의:

- `.env`, DB 비밀번호, API Key는 git에 올리지 않습니다.
- 운영에서는 `AWS_ACCESS_KEY_ID`, `AWS_SECRET_ACCESS_KEY`를 넣지 않고 Elastic Beanstalk EC2 Role 권한을 사용하는 것을 권장합니다.
- 캡처/채팅/GitHub에 노출된 키는 재발급합니다.
- HTTPS와 커스텀 도메인을 붙인 뒤 보안 쿠키/SSL redirect 값을 다시 강화합니다.

---

## 테스트

```bash
python manage.py check
python manage.py test apps.users apps.logs apps.performances apps.recommendations apps.community
```

현재 로컬 `.venv`가 깨져 있으면 가상환경을 다시 생성한 뒤 실행합니다.

---

## 주요 기술

| 분류 | 기술 |
|---|---|
| Framework | Django 5.1, Django REST Framework |
| Auth | SimpleJWT, OAuth |
| Database | PostgreSQL |
| Infra | Docker, Elastic Beanstalk, RDS |
| Data | KOPIS OpenAPI |
| AI | OpenAI API |
| Async 예정 | Redis, Celery |
