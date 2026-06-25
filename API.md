# CulturePick API

CulturePick 백엔드 API 사용법을 정리한 문서입니다. 프로젝트 개요, 실행, 배포 방법은 [README.md](./README.md)를 확인하세요.

## 공통

운영 base URL 예시:

```text
http://culturepick.ap-northeast-2.elasticbeanstalk.com
```

API prefix:

```text
/api/v1/
```

인증이 필요한 API는 다음 헤더를 사용합니다.

```http
Authorization: Bearer <access_token>
```

JSON 요청은 기본적으로 다음 헤더를 사용합니다.

```http
Content-Type: application/json
```

헬스 체크:

```http
GET /health/
```

Response:

```json
{"status": "ok"}
```

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
  "nickname": "컬처러버"
}
```

Response `201`:

```json
{
  "message": "회원가입이 완료되었습니다."
}
```

Validation:

- 이메일 필수
- `@` 포함
- 이모지 금지
- 이메일 형식 검증
- 중복 이메일 금지
- 비밀번호 8자 이상
- 영문, 숫자, 특수문자 포함
- `password`와 `password_confirm` 일치

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
  "access": "...",
  "refresh": "..."
}
```

### 토큰 갱신

```http
POST /api/v1/auth/token/refresh/
```

Request:

```json
{
  "refresh": "..."
}
```

Response `200`:

```json
{
  "access": "...",
  "refresh": "..."
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
  "refresh": "..."
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
  "code": "authorization_code",
  "redirect_uri": "https://culturepick.netlify.app/auth/callback/google",
  "state": ""
}
```

지원 provider:

- `google`
- `kakao`
- `naver`

Response `200`:

```json
{
  "message": "로그인 성공",
  "access": "...",
  "refresh": "..."
}
```

## My Page API

### 내 프로필 조회

```http
GET /api/v1/auth/me/
Authorization: Bearer <access_token>
```

Response `200`:

```json
{
  "email": "user@example.com",
  "nickname": "",
  "display_name": "user@example.com",
  "phone": "",
  "provider": "local",
  "created_at": "2026-06-25T12:00:00+09:00",
  "updated_at": "2026-06-25T12:00:00+09:00",
  "can_change_password": true,
  "requires_password_verification": true
}
```

`display_name`은 닉네임이 있으면 닉네임, 없으면 이메일입니다.

### 비밀번호 재확인

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

Response `200`:

```json
{
  "verified": true,
  "verification_token": "...",
  "expires_in": 600
}
```

로컬 계정의 회원정보 수정 전에 호출합니다. 소셜 계정은 로컬 비밀번호가 없으므로 이 API를 사용할 수 없습니다.

### 프로필 수정

```http
PATCH /api/v1/auth/me/
Authorization: Bearer <access_token>
```

로컬 계정은 `verification_token`이 필요합니다.

Request:

```json
{
  "verification_token": "...",
  "nickname": "새닉네임",
  "phone": "010-0000-0000",
  "new_password": "NewPass123!",
  "new_password_confirm": "NewPass123!"
}
```

부분 수정이 가능합니다. 변경하지 않을 필드는 보내지 않아도 됩니다. 소셜 계정은 비밀번호 변경을 허용하지 않습니다.

### 관심 공연 목록

```http
GET /api/v1/auth/me/interests/
Authorization: Bearer <access_token>
```

Response `200`:

```json
{
  "type": "interest",
  "total": 2,
  "results": []
}
```

### 볼 예정 공연 목록

```http
GET /api/v1/auth/me/watchlist/
Authorization: Bearer <access_token>
```

Response `200`:

```json
{
  "type": "watchlist",
  "total": 2,
  "results": []
}
```

### 내가 작성한 게시글

```http
GET /api/v1/auth/me/posts/
Authorization: Bearer <access_token>
```

Query parameters:

| 이름 | 설명 | 예시 |
|---|---|---|
| `category` | 게시글 카테고리 | `performance_review` |
| `category_slug` | `category` alias | `information` |
| `keyword` | 제목/내용 검색 | `후기` |
| `search` | `keyword` alias | `레미제라블` |
| `q` | `keyword` alias | `주차` |

## Performance API

### 공연 목록/검색

```http
GET /api/v1/performances/
```

Query parameters:

| 이름 | 설명 | 예시 |
|---|---|---|
| `keyword` | 제목/출연진/공연장 키워드 | `레미제라블` |
| `genre` | 장르 코드 또는 alias | `GGGA`, `musical`, `CCCC`, `koreanMusic` |
| `local` | 지역 필터 | `seoul` |
| `region` | `local` alias | `seoul` |
| `status` | 상태 필터 | `upcoming`, `performing`, `done` |
| `sort` | 정렬 | `latest`, `popular`, `zzim`, `title` |
| `sorted` | `sort` alias | `latest` |
| `pageNum` | 페이지 번호 | `1` |
| `page` | `pageNum` alias | `1` |
| `pageSize` | 페이지 크기 | `20` |
| `page_size` | `pageSize` alias | `20` |

장르 예시:

| 요청값 | 의미 |
|---|---|
| `AAAA`, `play` | 연극 |
| `GGGA`, `musical` | 뮤지컬 |
| `CCCA`, `classic` | 클래식/서양음악 |
| `CCCC`, `koreanMusic` | 한국음악/국악 |
| `CCCD`, `concert` | 대중음악 |
| `BBBC`, `dancing` | 무용/댄스 |

Response `200`:

```json
{
  "pageNum": 1,
  "pageSize": 20,
  "total": 100,
  "searchData": [
    {
      "performance_id": "PF...",
      "title": "공연명",
      "genre": "뮤지컬",
      "genre_code": "GGGA",
      "start_date": "2026-06-01",
      "end_date": "2026-08-31",
      "status": "공연중",
      "poster_url": "https://...",
      "runtime": "120분",
      "age_rating": "만 7세 이상",
      "min_price": 30000,
      "max_price": 150000,
      "is_free": false,
      "price_options": [
        {
          "label": "R석",
          "price": 150000,
          "currency": "KRW",
          "raw_text": "R석 150,000원",
          "sort_order": 0
        }
      ],
      "venue": {
        "venue_id": "FC...",
        "name": "공연장",
        "sido": "서울특별시",
        "gugun": "종로구",
        "address": "서울특별시 ..."
      },
      "view_count": 0,
      "zzim_count": 0,
      "is_interested": false,
      "is_watchlisted": false
    }
  ],
  "page": 1,
  "page_size": 20,
  "results": []
}
```

`searchData`와 `results`는 같은 목록 데이터를 제공합니다.

### 공연 상세

```http
GET /api/v1/performances/{performance_id}/
```

Response에는 목록 필드에 더해 다음 정보가 포함됩니다.

- `synopsis`
- `schedule_info`
- `images`
- `booking_links`
- `cast`
- `crew`
- `production_company`
- `agency`
- `host`
- `organizer`

상세 조회 시 view log가 저장됩니다.

### 관심/볼예정 등록 및 해제

```http
POST /api/v1/performances/{performance_id}/actions/
Authorization: Bearer <access_token>
```

Request:

```json
{
  "action_type": "interest",
  "is_active": true
}
```

필드:

| 이름 | 설명 |
|---|---|
| `action_type` | `interest` 또는 `watchlist` |
| `is_active` | `true`면 등록, `false`면 해제, 생략하면 toggle |

Response `200`:

```json
{
  "performance_id": "PF...",
  "action_type": "interest",
  "is_active": true,
  "is_interested": true,
  "is_watchlisted": false,
  "zzim_count": 3
}
```

`zzim_count`는 모든 사용자의 `interest` 등록 수입니다.

## Community API

### 게시글 카테고리

| 화면명 | 요청/저장값 |
|---|---|
| 공연후기 | `performance_review` |
| 공연추천 | `performance_recommendation` |
| 정보공유 | `information` |
| 자유토론 | `free_discussion` |

### 게시글 목록

```http
GET /api/v1/community/posts/
```

Query parameters:

| 이름 | 설명 | 예시 |
|---|---|---|
| `category` | 카테고리 | `performance_review` |
| `category_slug` | `category` alias | `information` |
| `keyword` | 제목/내용 검색 | `후기` |
| `search` | `keyword` alias | `레미제라블` |
| `q` | `keyword` alias | `주차` |

Response item 주요 필드:

```json
{
  "id": 1,
  "author": 1,
  "author_email": "user@example.com",
  "author_nickname": "닉네임",
  "author_display_name": "닉네임",
  "category": "performance_review",
  "category_label": "performance_review",
  "title": "레미제라블 후기",
  "content": "<p>본문</p>",
  "content_format": "html",
  "thumbnail_url": "https://...",
  "view_count": 10,
  "comment_count": 2,
  "created_at": "2026-06-25T12:00:00+09:00",
  "updated_at": "2026-06-25T12:00:00+09:00"
}
```

### 게시글 작성

```http
POST /api/v1/community/posts/
Authorization: Bearer <access_token>
```

Request:

```json
{
  "category": "performance_review",
  "title": "레미제라블 후기",
  "content": "<p>좋았습니다.</p>",
  "content_format": "html",
  "thumbnail_url": "https://..."
}
```

`content_format`:

- `html`
- `markdown`
- `json`

### 게시글 상세

```http
GET /api/v1/community/posts/{id}/
```

상세 조회 시 `view_count`가 증가합니다.

### 게시글 수정

```http
PATCH /api/v1/community/posts/{id}/
Authorization: Bearer <access_token>
```

작성자만 수정할 수 있습니다.

### 게시글 삭제

```http
DELETE /api/v1/community/posts/{id}/
Authorization: Bearer <access_token>
```

작성자만 삭제할 수 있습니다.

### 댓글 목록

```http
GET /api/v1/community/posts/{post_id}/comments/
```

### 댓글 작성

```http
POST /api/v1/community/posts/{post_id}/comments/
Authorization: Bearer <access_token>
```

Request:

```json
{
  "content": "댓글 내용"
}
```

### 댓글 수정/삭제

```http
PATCH /api/v1/community/comments/{id}/
DELETE /api/v1/community/comments/{id}/
Authorization: Bearer <access_token>
```

작성자만 수정/삭제할 수 있습니다.

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

또는:

```text
file=<file>
```

허용 타입:

- `image/jpeg`
- `image/png`
- `image/webp`
- `image/gif`

최대 크기: 5MB

Response `201`:

```json
{
  "id": 1,
  "image": "community/images/2026/06/25/....png",
  "image_url": "https://bucket.s3.ap-northeast-2.amazonaws.com/community/images/2026/06/25/....png",
  "url": "https://bucket.s3.ap-northeast-2.amazonaws.com/community/images/2026/06/25/....png",
  "original_name": "poster.png",
  "size": 12345,
  "content_type": "image/png",
  "created_at": "2026-06-25T12:00:00+09:00"
}
```

프론트 에디터는 `url` 또는 `image_url`을 본문에 삽입하면 됩니다.

## Logs API

로그 API는 추천 데이터 학습과 사용자 행동 분석에 사용됩니다. 공연 목록 검색, 상세 조회, 관심/볼예정 액션에서는 일부 로그가 서버에서 자동 저장됩니다.

### 검색 로그

```http
POST /api/v1/logs/search/
```

Request:

```json
{
  "keyword": "레미제라블",
  "filter_region": "seoul",
  "filter_genre": "GGGA",
  "filter_status": "performing"
}
```

### 조회 로그

```http
POST /api/v1/logs/view/
```

Request:

```json
{
  "performance_id": "PF...",
  "log_type": "detail"
}
```

### QnA 로그

```http
POST /api/v1/logs/qna/
```

Request:

```json
{
  "question": "가족과 보기 좋은 공연 추천해줘",
  "answer": "추천 응답 내용"
}
```

## Recommendations API

### 추천 후보 조회

```http
POST /api/v1/recommendations/candidates/
```

Request:

```json
{
  "message": "가족과 보기 좋은 공연 추천해줘",
  "limit": 10
}
```

Response `200`:

```json
{
  "message": "가족과 보기 좋은 공연 추천해줘",
  "profile": {},
  "total": 10,
  "candidates": [
    {
      "performance": {},
      "score": 3.2,
      "reasons": ["가족 관람 조건과 맞습니다."],
      "contributions": []
    }
  ]
}
```

### AI 추천

```http
POST /api/v1/recommendations/ai/
Authorization: Bearer <access_token>
```

Request:

```json
{
  "message": "시간 없을 때 보기 좋은 공연 추천해줘",
  "limit": 3,
  "candidate_limit": 8,
  "include_candidates": false
}
```

필드:

| 이름 | 설명 | 기본값 |
|---|---|---|
| `message` | 사용자 요청 문장 | `""` |
| `prompt` | `message` alias | `""` |
| `limit` | 최종 추천 개수, 1~10 | `5` |
| `candidate_limit` | AI에 전달할 후보 수, 3~20 | 환경변수 기본값 |
| `session_id` | 이전 추천 세션 참조 | `null` |
| `include_candidates` | 디버그용 후보/프로필 포함 | `false` |

Response `200`:

```json
{
  "session_id": 1,
  "summary": "요청에 맞는 공연을 골라봤어요.",
  "message": "요청에 맞는 공연을 골라봤어요.",
  "fallback_used": false,
  "validation_status": "passed",
  "constraint_notes": [],
  "recommendations": [
    {
      "performance_id": "PF...",
      "title": "공연명",
      "reason": "추천 이유",
      "rank": 1,
      "source": "openai",
      "score": 3.2
    }
  ],
  "results": []
}
```

`recommendations`는 프론트 카드 표시용 요약 배열이고, `results`는 공연 카드 렌더링에 필요한 상세 정보가 포함된 배열입니다.

AI 호출 실패 또는 quota 부족 시 rule-based fallback 응답을 반환합니다.

### 추천 피드백 저장

```http
POST /api/v1/recommendations/{session_id}/feedback/
Authorization: Bearer <access_token>
```

Request:

```json
{
  "performance_id": "PF...",
  "feedback_type": "booking_link",
  "metadata": {
    "source": "recommendation_card"
  }
}
```

`feedback_type`:

- `click`
- `interest`
- `watchlist`
- `booking_link`
- `thumbs_up`
- `thumbs_down`
- `regenerate`
- `reason_not_helpful`
- `not_my_taste`
- `already_seen`

피드백 점수:

| 행동 | 점수 |
|---|---:|
| 상세 클릭 | 1 |
| 관심 등록 | 3 |
| 볼예정 등록 | 5 |
| 예매 링크 클릭 | 8 |
| 좋아요 | 4 |
| 싫어요 | -6 |
| 재추천 요청 | -3 |
| 추천 이유 불만족 | -6 |
| 취향 아님 | -4 |
| 이미 봄 | -2 |

`no_interaction`은 현재 점수 산출에서 제외했습니다.

## 상태 코드와 오류

자주 발생하는 상태 코드:

| 상태 | 의미 |
|---|---|
| `200` | 성공 |
| `201` | 생성 성공 |
| `204` | 삭제 성공 |
| `400` | 요청값 검증 실패 |
| `401` | 인증 필요 |
| `403` | 권한 없음 |
| `404` | 리소스 없음 |
| `500` | 서버 오류 |

오류 응답은 DRF validation error 형태를 따릅니다.

예:

```json
{
  "email": ["Email is already registered."]
}
```

또는:

```json
{
  "detail": "Authentication credentials were not provided."
}
```

