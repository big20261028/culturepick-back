from django.core.management.base import BaseCommand

from apps.performances.models import Venue
from django.db.models import Q

SIDO_NORMALIZE = {
    "서울특별시": "서울",
    "부산광역시": "부산",
    "대구광역시": "대구",
    "인천광역시": "인천",
    "광주광역시": "광주",
    "대전광역시": "대전",
    "울산광역시": "울산",
    "세종특별자치시": "세종",
    "경기도": "경기",
    "강원도": "강원",
    "강원특별자치도": "강원",
    "충청북도": "충북",
    "충청남도": "충남",
    "전라북도": "전북",
    "전북특별자치도": "전북",
    "전라남도": "전남",
    "경상북도": "경북",
    "경상남도": "경남",
    "제주특별자치도": "제주",
    "부산부산광역시": "부산", 
    "태국": "해외",
}


def extract_region(address: str) -> tuple[str, str]:
    if not address or not address.strip() or address.strip() == "-":
        return "", ""          # ← "-" 도 빈 주소로 처리

    parts = address.strip().split()
    if len(parts) < 1:
        return "", ""

    raw_sido = parts[0]
    sido = SIDO_NORMALIZE.get(raw_sido, raw_sido)
    gugun = parts[1] if len(parts) > 1 else ""

    if gugun and not any(gugun.endswith(s) for s in ["시", "구", "군"]):
        gugun = ""

    return sido, gugun


class Command(BaseCommand):
    help = "Fill sido/gugun from address"

    def handle(self, *args, **options):
        # venues = Venue.objects.filter(sido="")
        venues = Venue.objects.filter(
            Q(sido="") | Q(sido="-") | Q(sido="부산부산광역시") | Q(sido="태국") | Q(sido="미분류")
        )
        total = venues.count()
        print(f"target: {total}")

        updated = 0
        skipped = 0

        for venue in venues:
            sido, gugun = extract_region(venue.address)
            if not sido:
                venue.sido = "미분류"
                venue.gugun = ""
                venue.save(update_fields=["sido", "gugun"])
                skipped += 1  # ← 이건 그대로 둬도 되고
                continue
            venue.sido = sido
            venue.gugun = gugun
            venue.save(update_fields=["sido", "gugun"])
            updated += 1

        print(f"done: updated={updated} skipped={skipped}")