import requests
from rest_framework.exceptions import AuthenticationFailed
from django.conf import settings

def get_kakao_info(code, redirect_uri):
    access_token = get_kakao_access_token(code, redirect_uri)
    headers = {"Authorization": f"Bearer {access_token}"}
    res = requests.get("https://kapi.kakao.com/v2/user/me", headers=headers)
    if res.status_code != 200: raise AuthenticationFailed("카카오 토큰이 유효하지 않습니다.")
    
    data = res.json()
    account = data.get("kakao_account", {})

    email = account.get("email")
    if not email:
        raise AuthenticationFailed("이메일 제공에 동의해주세요.")

    return {
        "provider_id": str(data.get("id")),
        "email": email,
        "nickname": account.get("profile", {}).get("nickname", "")
    }

def get_naver_info(code, state):
    access_token = get_naver_access_token(code, state)
    headers = {"Authorization": f"Bearer {access_token}"}
    res = requests.get("https://openapi.naver.com/v1/nid/me", headers=headers)
    if res.status_code != 200: raise AuthenticationFailed("네이버 토큰이 유효하지 않습니다.")
    
    # 네이버는 데이터가 'response' 안에 한 번 더 감싸져 있습니다.
    data = res.json().get("response", {})

    email = data.get("email")
    if not email:
        raise AuthenticationFailed("이메일 제공에 동의해주세요.")
    
    return {
        "provider_id": data.get("id"),
        "email": email,
        "nickname": data.get("name", "")
    }

def get_google_info(code, redirect_uri):
    access_token = get_google_access_token(code, redirect_uri)
    headers = {"Authorization": f"Bearer {access_token}"}
    res = requests.get("https://www.googleapis.com/oauth2/v3/userinfo", headers=headers)
    if res.status_code != 200: raise AuthenticationFailed("구글 토큰이 유효하지 않습니다.")
    
    data = res.json()

    email = data.get("email")
    if not email:
        raise AuthenticationFailed("이메일 제공에 동의해주세요.")
    
    return {
        # 구글은 고유 ID를 'sub'라는 키로 줍니다.
        "provider_id": str(data.get("sub")),
        "email": email,
        "nickname": data.get("name", "")
    }

# def _get_social_info(url, access_token, parser):
#     headers = {"Authorization": f"Bearer {access_token}"}
#     res = requests.get(url, headers=headers)
#     if res.status_code != 200:
#         raise AuthenticationFailed("소셜 토큰이 유효하지 않습니다.")
#     return parser(res.json())

# A방식 추가 함수 - code로 액세스토큰을 먼저 받아옴
def get_kakao_access_token(code, redirect_uri):
    res = requests.post(
        "https://kauth.kakao.com/oauth/token",
        data={
            "grant_type": "authorization_code",
            "client_id": settings.SOCIAL_AUTH_KAKAO_KEY,
            "redirect_uri": redirect_uri,
            "code": code,
        }
    )
    if res.status_code != 200:
        raise AuthenticationFailed("카카오 인가코드가 유효하지 않습니다.")

    access_token = res.json().get("access_token")
    if not access_token:
        raise AuthenticationFailed("액세스토큰을 받아오지 못했습니다.")
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
        }
    )
    if res.status_code != 200:
        raise AuthenticationFailed("네이버 인가코드가 유효하지 않습니다.")
    return res.json().get("access_token")


def get_google_access_token(code, redirect_uri):
    res = requests.post(
        "https://oauth2.googleapis.com/token",
        data={
            "grant_type": "authorization_code",
            "client_id": settings.SOCIAL_AUTH_GOOGLE_OAUTH2_KEY,
            "client_secret": settings.SOCIAL_AUTH_GOOGLE_OAUTH2_SECRET,
            "redirect_uri": redirect_uri,
            "code": code,
        }
    )
    if res.status_code != 200:
        raise AuthenticationFailed("구글 인가코드가 유효하지 않습니다.")
    return res.json().get("access_token")