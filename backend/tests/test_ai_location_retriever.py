"""Campus directory validation and multilingual location retrieval tests."""

import json

from app.ai.knowledge.location_retriever import (
    DATA_PATH,
    find_location,
    find_locations,
    load_locations,
)


def match_ids(query: str, locale: str = "ko") -> list[str]:
    return [match.location.location_id for match in find_locations(query, locale=locale)]


def test_directory_has_unique_ids_localized_names_and_aliases() -> None:
    payload = json.loads(DATA_PATH.read_text(encoding="utf-8"))
    entries = payload["locations"]
    ids = [entry["id"] for entry in entries]

    assert len(entries) >= 60
    assert len(ids) == len(set(ids))
    assert {entry["campus"] for entry in entries} == {"HSSC", "NSC"}
    for entry in entries:
        assert entry["names"]["ko"].strip()
        assert entry["names"]["en"].strip()
        for aliases in entry.get("aliases", {}).values():
            normalized = ["".join(alias.lower().split()) for alias in aliases]
            assert len(normalized) == len(set(normalized))


def test_loader_preserves_campus_and_building_number() -> None:
    locations = {location.location_id: location for location in load_locations()}

    assert locations["hssc_student_center"].campus == "HSSC"
    assert locations["nsc_student_center"].campus == "NSC"
    assert locations["nsc_samsung_library"].building_number == "48"


def test_korean_and_english_names_and_aliases_are_searchable() -> None:
    assert match_ids("중도에서 지갑을 잃어버렸어요") == ["hssc_central_library"]
    assert match_ids("I found it at Samsung Library", locale="en") == ["nsc_samsung_library"]
    assert match_ids("기학 앞에서 주웠어요") == ["nsc_general_studies_building"]


def test_multiple_locations_follow_sentence_order_and_infer_campus() -> None:
    matches = find_locations("삼성학술정보관과 학생회관 사이에서 잃어버렸어요")

    assert [match.location.location_id for match in matches] == [
        "nsc_samsung_library",
        "nsc_student_center",
    ]


def test_more_specific_location_suppresses_contained_name() -> None:
    assert match_ids("수선관 별관 3층") == ["hssc_suseon_hall_annex"]
    match = find_locations("수선관 별관 3층")[0]
    assert match.resolved_name == "수선관 별관 3층"


def test_explicit_campus_hint_resolves_shared_location_name() -> None:
    assert match_ids("율전 학생회관에서 만나요") == ["nsc_student_center"]
    assert match_ids("명륜 학생회관에서 찾았어요") == ["hssc_student_center"]
    assert match_ids("At the Suwon campus Student Center", locale="en") == [
        "nsc_student_center"
    ]


def test_shared_name_without_campus_remains_ambiguous() -> None:
    assert set(match_ids("학생회관에서 주웠어요")) == {
        "hssc_student_center",
        "nsc_student_center",
    }
    assert find_location("학생회관에서 주웠어요") is None


def test_floor_formats_are_preserved() -> None:
    assert find_locations("경영관 지하 3층")[0].resolved_name == "경영관 지하3층"
    assert find_locations("N센터 B1층", locale="ko")[0].resolved_name == "N센터 B1층"


def test_unknown_or_too_short_text_does_not_match() -> None:
    assert find_locations("학교 근처 어딘가") == ()
    assert find_locations("관") == ()
