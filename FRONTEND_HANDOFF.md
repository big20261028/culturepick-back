# CulturePick Frontend Handoff

백엔드 기능이 추가되거나 API 계약이 바뀔 때 프론트엔드 담당자에게 전달할 작업을
한곳에서 관리하는 문서입니다. 완료한 항목은 체크하고, API가 바뀌면 같은 변경에서
이 문서도 함께 수정합니다.

- 백엔드 저장소: `culturepick-back`
- 참고 프론트: `13-pjt/culturepick-front-user`
- 프론트 운영 주소: `https://culturepick.netlify.app`
- API 계약 상세: `API.md`
- 최종 수정일: 2026-07-23

## 상태 표기

- `[ ]` 시작 전
- `[-]` 진행 중
- `[x]` 완료 및 운영 확인
- `BLOCKED` 백엔드 또는 인프라 선행 작업 필요

## P0 — 비밀번호 재설정 및 계정 찾기

현재 백엔드 API는 구현됐지만 프론트 라우트와 화면이 없어 사용자가 메일 링크에서
재설정을 끝낼 수 없습니다. `SiteRouter.findAccount = '/find-account'` 상수는 이미
있지만 `src/router/index.ts`에는 실제 route가 없습니다.

### 1. API 타입과 호출 함수

- [ ] `src/types/auth.ts`에 아래 요청·응답 타입 추가
- [ ] `src/api/auth.ts`에 아래 3개 API 함수 추가
- [ ] 공개 API이므로 access token을 요구하지 않도록 구현

#### 재설정 메일 요청

```http
POST /api/v1/auth/password/reset/request/
Content-Type: application/json

{
  "email": "user@example.com"
}
```

성공 응답은 이메일 가입 여부와 관계없이 항상 같은 형태입니다.

```json
{
  "message": "재설정 가능한 계정이면 입력한 이메일로 안내를 발송했습니다."
}
```

존재하지 않는 이메일이라고 별도 안내하지 마세요. 성공 화면에는 “가입된 계정인
경우 메일이 발송됩니다”라고 표시합니다.

#### 새 비밀번호 확정

```http
POST /api/v1/auth/password/reset/confirm/
Content-Type: application/json

{
  "uid": "MQ",
  "token": "...",
  "new_password": "NewValidPass456!",
  "new_password_confirm": "NewValidPass456!"
}
```

```json
{
  "message": "비밀번호가 재설정되었습니다. 새 비밀번호로 로그인해주세요."
}
```

`400` 응답은 만료·사용 완료·변조된 링크 또는 비밀번호 정책 실패를 의미합니다.
서버의 상세 오류가 있으면 입력 필드 아래에 표시하고, 토큰 오류는 새 재설정 메일을
요청할 수 있는 버튼과 함께 안내합니다.

#### 가입 방식 찾기

```http
POST /api/v1/auth/account/recovery/
Content-Type: application/json

{
  "email": "user@example.com"
}
```

```json
{
  "message": "안내 가능한 계정이면 입력한 이메일로 가입 정보를 발송했습니다."
}
```

이 API도 가입 여부를 공개하지 않습니다. 실제 가입 방식은 이메일 소유자에게만
발송됩니다.

### 2. 라우트와 화면

- [ ] `src/router/index.ts`의 catch-all route보다 앞에 `/find-account` 추가
- [ ] `src/views/auth/FindAccountView.vue` 또는 같은 역할의 화면 추가
- [ ] 로그인 화면에 “비밀번호/계정 찾기” 링크 추가
- [ ] `AuthLayout`, 기존 `AuthCard`, 비밀번호 검증 composable 재사용

한 화면에서 query parameter에 따라 모드를 나누는 것을 권장합니다.

1. `uid`, `token`이 모두 없음: 이메일 입력 및 재설정/가입 방식 안내 요청
2. `uid`, `token`이 모두 있음: 새 비밀번호 입력 및 확정
3. 둘 중 하나만 있음: 잘못된 링크 안내 후 새 메일 요청 버튼 표시

메일 링크 형식:

```text
https://culturepick.netlify.app/find-account?uid=<uid>&token=<token>
```

`uid`와 `token`을 브라우저 로그, 분석 이벤트, 오류 추적 태그에 남기지 마세요.
확정 요청이 끝난 뒤에는 query parameter가 없는 로그인 화면으로 이동합니다.

### 3. 비밀번호 입력 정책

- [ ] 기존 회원가입용 `usePasswordValidation`을 재사용
- [ ] 비밀번호/확인값 일치 검사
- [ ] 제출 중 중복 클릭 방지
- [ ] 성공 후 브라우저에 남아 있는 access/refresh token 제거
- [ ] 로그인 화면으로 이동하고 “새 비밀번호로 로그인해주세요” 안내

## P0 — 인증 세션 만료 처리

백엔드는 사용자별 `auth_version`을 JWT와 비교합니다. 비밀번호가 변경되면 그
사용자의 이전 access/refresh token만 무효가 됩니다. 로그인 API의 JSON 계약은
그대로이므로 토큰 해석 코드를 추가할 필요는 없습니다.

- [ ] API가 `401`을 반환하면 기존 refresh 시도를 수행
- [ ] refresh도 실패하면 access/refresh cookie를 모두 삭제
- [ ] 로그인 화면으로 이동하면서 원래 경로를 redirect 값으로 보존
- [ ] “보안을 위해 다시 로그인해주세요” 메시지 표시

현재 `src/api/client.ts`와 `src/utils/auth-session.ts`에 유사한 처리가 있으므로 새
별도 인터셉터를 만들기보다 기존 경로를 검증합니다.

## P1 — 비활성 계정 복구

백엔드에는 `deactivation_reason`, `deactivated_at`이 추가되지만 공개 재활성화 API는
아직 제공하지 않습니다.

- `self_deactivated`: 사용자가 직접 탈퇴/비활성화한 상태로, 추후 본인 확인을 거쳐
  복구 기능을 제공할 수 있는 유일한 후보
- `admin_disabled`, `security_lock`, `policy_banned`: 관리자·보안·정책 판단이 필요한
  상태이므로 사용자 화면에서 자동 복구 금지

따라서 현재 프론트에서는 “비활성 계정 복구” 버튼을 만들지 않습니다. 백엔드의
재활성화 토큰/확정 API 계약이 추가된 뒤 이 문서에 별도 P0 작업으로 등록합니다.

## P1 — 커뮤니티 이미지

서버는 게시글 HTML의 이미지 주소를 `/media/` 또는 승인된 S3/CDN HTTPS 호스트로
제한합니다.

- [ ] 에디터 이미지는 반드시 `POST /api/v1/community/images/`로 먼저 업로드
- [ ] 응답의 `url` 또는 `image_url`만 `<img src>`에 사용
- [ ] 사용자가 입력한 외부 이미지 URL을 본문에 직접 삽입하지 않기
- [ ] HTTP 이미지 URL을 HTTPS로 임의 변환하지 말고 업로드 API 사용

## BLOCKED — 운영 API HTTPS

Netlify 화면은 HTTPS이므로 HTTP API 호출은 브라우저에서 차단됩니다. 운영 API의
최종 HTTPS 주소가 결정되기 전까지 `VITE_API_BASE_URL` 운영값 확정은 보류합니다.

HTTPS 주소가 준비되면:

- [ ] Netlify `VITE_API_BASE_URL`을 새 HTTPS API 주소로 변경
- [ ] CORS origin이 `https://culturepick.netlify.app`인지 확인
- [ ] 로그인, token refresh, 이미지 업로드, 비밀번호 재설정 E2E 확인
- [ ] 브라우저 Network 탭에서 mixed-content 오류가 없는지 확인

## 완료 조건

- [ ] 미가입 이메일 요청도 UI가 계정 존재 여부를 노출하지 않음
- [ ] 실제 로컬 계정이 재설정 메일을 받고 새 비밀번호로 로그인 가능
- [ ] 만료·재사용 토큰이 친절한 오류 화면으로 연결됨
- [ ] Google/Kakao/Naver 가입 사용자가 이메일로 가입 방식을 확인 가능
- [ ] 비밀번호 변경 전 토큰이 `401`이 되면 프론트가 로그인으로 안전하게 이동
- [ ] 모바일 화면과 키보드 접근성 확인
- [ ] token, 이메일, 새 비밀번호가 console/analytics/error tracking에 남지 않음

## 변경 기록

| 날짜 | 백엔드 변경 | 프론트 영향 |
|---|---|---|
| 2026-07-23 | 비밀번호 재설정·가입 방식 안내 API | `/find-account` 화면과 API 연동 필요 |
| 2026-07-23 | `auth_version` 기반 JWT 폐기 | 기존 JSON 계약 유지, 401/refresh 실패 UX 확인 |
| 2026-07-23 | 서버 HTML·이미지 호스트 허용 목록 | 업로드 API가 반환한 이미지 URL만 사용 |
