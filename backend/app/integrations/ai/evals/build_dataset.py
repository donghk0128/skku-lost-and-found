"""Build a deterministic 100-case Korean baseline seed dataset."""

import json
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from core.schemas import DraftRequest, GoldCase, PostDraft


CATEGORIES = [
    ("ELECTRONICS", "에어팟", "검은색 케이스"),
    ("WALLET", "지갑", "갈색 가죽"),
    ("ID_CARD", "학생증", "파란색 카드 케이스"),
    ("BAG", "백팩", "회색 천 소재"),
    ("CLOTHING", "목도리", "빨간색 줄무늬"),
    ("KEY", "열쇠", "곰 모양 키링"),
    ("BOOK_STATIONERY", "전공책", "노란색 표지"),
    ("OTHER", "텀블러", "은색 금속"),
]
LOCATIONS = ["삼성학술정보관 2층", "학생회관 1층", "경영관 3층", "제2공학관 로비", "중앙학술정보관 앞"]
KST = timezone(timedelta(hours=9))
REFERENCE = datetime(2026, 10, 18, 18, 0, tzinfo=KST)


def build_case(index: int) -> GoldCase:
    code, item, trait = CATEGORIES[index % len(CATEGORIES)]
    post_type = "LOST" if index < 50 else "FOUND"
    location = LOCATIONS[index % len(LOCATIONS)]
    ambiguous_location = index % 10 == 0
    missing_time = index % 10 == 1
    verb = "잃어버렸어요" if post_type == "LOST" else "주웠어요"
    when = REFERENCE - timedelta(days=index % 3, hours=index % 5)
    natural_location = "여기에서" if ambiguous_location else f"{location}에서"
    time_phrase = "언젠가" if missing_time else when.strftime("%m월 %d일 %H시쯤")
    text = f"{time_phrase} {natural_location} {trait} {item}을 {verb}. 혹시 관련된 분은 확인 부탁드려요."
    title_action = "분실" if post_type == "LOST" else "습득"
    expected_location = None if ambiguous_location else location
    start = None if missing_time else when - timedelta(minutes=15)
    end = None if missing_time else when + timedelta(minutes=15)
    missing = []
    warnings = []
    if ambiguous_location:
        missing.append("location")
        warnings.append("현재 위치 표현만 있어 장소 확인이 필요합니다.")
    if missing_time:
        missing.append("event_time")
        warnings.append("정확한 발생 시간 확인이 필요합니다.")
    return GoldCase(
        id=f"case-{index + 1:03d}",
        request=DraftRequest(post_type=post_type, natural_language=text, reference_time=REFERENCE),
        expected=PostDraft(
            title=f"{item} {title_action}",
            description=f"{trait} {item} 관련 게시글입니다.",
            item_name=item,
            category_code=code,
            location_text=expected_location,
            event_start_at=start,
            event_end_at=end,
            keywords=[trait, item],
            missing_fields=missing,
            warnings=warnings,
        ),
    )


def main() -> None:
    output = Path(__file__).with_name("dataset.jsonl")
    cases = [build_case(index) for index in range(100)]
    output.write_text(
        "\n".join(case.model_dump_json() for case in cases) + "\n",
        encoding="utf-8",
    )
    print(f"Wrote {len(cases)} cases to {output}")


if __name__ == "__main__":
    main()
