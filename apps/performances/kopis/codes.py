from __future__ import annotations


GENRE_NAME_TO_CODE = {
    "연극": "AAAA",
    "무용(서양/한국무용)": "BBBC",
    "대중무용": "BBBE",
    "서양음악(클래식)": "CCCA",
    "한국음악(국악)": "CCCC",
    "대중음악": "CCCD",
    "복합": "EEEA",
    "서커스/마술": "EEEB",
    "뮤지컬": "GGGA",
}

STATUS_NAME_TO_CODE = {
    "공연예정": "01",
    "공연중": "02",
    "공연완료": "03",
}


def genre_code_from_name(name: str) -> str:
    return GENRE_NAME_TO_CODE.get(name.strip(), "")


def status_code_from_name(name: str) -> str:
    return STATUS_NAME_TO_CODE.get(name.strip(), "")
