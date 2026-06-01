import requests
from django.conf import settings
from rest_framework.exceptions import AuthenticationFailed

REQUEST_TIMEOUT = 10


def get_kakao_info(code, redirect_uri):
    access_token = get_kakao_access_token(code, redirect_uri)
    headers = {"Authorization": f"Bearer {access_token}"}
    res = requests.get("https://kapi.kakao.com/v2/user/me", headers=headers, timeout=REQUEST_TIMEOUT)
    if res.status_code != 200:
        raise AuthenticationFailed("카카오 토큰이 유효하지 않습니다.")

    data = res.json()
    account = data.get("kakao_account", {})

    email = account.get("email")
    if not email:
        raise AuthenticationFailed("이메일 제공에 동의해주세요.")

    return {
        "provider_id": str(data.get("id")),
        "email": email,
        "nickname": account.get("profile", {}).get("nickname", ""),
    }


def get_naver_info(code, state):
    access_token = get_naver_access_token(code, state)
    headers = {"Authorization": f"Bearer {access_token}"}
    res = requests.get("https://openapi.naver.com/v1/nid/me", headers=headers, timeout=REQUEST_TIMEOUT)
    if res.status_code != 200:
        raise AuthenticationFailed("네이버 토큰이 유효하지 않습니다.")

    data = res.json().get("response", {})

    email = data.get("email")
    if not email:
        raise AuthenticationFailed("이메일 제공에 동의해주세요.")

    return {
        "provider_id": str(data.get("id")),
        "email": email,
        "nickname": data.get("name", ""),
    }


def get_google_info(code, redirect_uri):
    access_token = get_google_access_token(code, redirect_uri)
    headers = {"Authorization": f"Bearer {access_token}"}

    try:
        res = requests.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers=headers,
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise AuthenticationFailed("구글 사용자 정보 조회에 실패했습니다.") from exc

    if res.status_code != 200:
        raise AuthenticationFailed("구글 토큰이 유효하지 않습니다.")

    data = res.json()
    email = data.get("email")
    provider_id = data.get("sub")

    if not email:
        raise AuthenticationFailed("이메일 제공에 동의해주세요.")
    if data.get("email_verified") is False:
        raise AuthenticationFailed("구글 이메일 인증이 완료되지 않은 계정입니다.")
    if not provider_id:
        raise AuthenticationFailed("구글 계정 식별자를 확인할 수 없습니다.")

    return {
        "provider_id": str(provider_id),
        "email": email,
        "nickname": data.get("name", ""),
    }


def get_kakao_access_token(code, redirect_uri):
    res = requests.post(
        "https://kauth.kakao.com/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": settings.SOCIAL_AUTH_KAKAO_KEY,
            "redirect_uri": redirect_uri,
            "code": code,
        },
        timeout=REQUEST_TIMEOUT,
    )
    if res.status_code != 200:
        raise AuthenticationFailed("카카오 인가 코드가 유효하지 않습니다.")

    access_token = res.json().get("access_token")
    if not access_token:
        raise AuthenticationFailed("카카오 액세스 토큰을 받아오지 못했습니다.")
    return access_token


def get_naver_access_token(code, state):
    res = requests.post(
        "https://nid.naver.com/oauth2.0/token",
        data={
            "grant_type": "authorization_code",
            "client_id": settings.SOCIAL_AUTH_NAVER_KEY,
            "client_secret": settings.SOCIAL_AUTH_NAVER_SECRET,
            "code": code,
            "state": state,
        },
        timeout=REQUEST_TIMEOUT,
    )
    if res.status_code != 200:
        raise AuthenticationFailed("네이버 인가 코드가 유효하지 않습니다.")

    access_token = res.json().get("access_token")
    if not access_token:
        raise AuthenticationFailed("네이버 액세스 토큰을 받아오지 못했습니다.")
    return access_token


def get_google_access_token(code, redirect_uri):
    if not settings.SOCIAL_AUTH_GOOGLE_OAUTH2_KEY or not settings.SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET:
        raise AuthenticationFailed("구글 로그인 설정이 완료되지 않았습니다.")

    try:
        res = requests.post(
            "https://oauth2.googleapis.com/token",
            data={
                "grant_type": "authorization_code",
                "client_id": settings.SOCIAL_AUTH_GOOGLE_OAUTH2_KEY,
                "client_secret": settings.SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET,
                "redirect_uri": redirect_uri,
                "code": code,
            },
            timeout=REQUEST_TIMEOUT,
        )
    except requests.RequestException as exc:
        raise AuthenticationFailed("구글 인증 서버와 통신하지 못했습니다.") from exc

    if res.status_code != 200:
        raise AuthenticationFailed("구글 인가 코드가 유효하지 않습니다.")

    access_token = res.json().get("access_token")
    if not access_token:
        raise AuthenticationFailed("구글 액세스 토큰을 받아오지 못했습니다.")
    return access_token
