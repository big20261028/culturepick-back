from django.shortcuts import render

# Create your views here.
# 서비스에서 보여줄 장르 → KOPIS 코드 매핑
SERVICE_GENRE_MAP = {
    "뮤지컬":  ["GGGA"],
    "연극":    ["AAAA"],
    "콘서트":  ["CCCD", "CCCA", "CCCC"],  # ← 이것만 추가하면 됨
    "무용":    ["BBBC", "BBBE"],
    "기타":    ["EEEA", "EEEB"],
}