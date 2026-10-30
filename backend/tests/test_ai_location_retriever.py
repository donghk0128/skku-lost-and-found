"""Verify deterministic campus alias retrieval without a model call."""

from app.integrations.ai.knowledge.location_retriever import (
    CampusLocation,
    find_location,
    find_locations,
)


LOCATIONS = (
    CampusLocation("삼성학술정보관", ("디도", "삼성도서관")),
    CampusLocation("학생회관", ("학관",)),
)


def test_sentence_search_preserves_floor_and_returns_all_candidates() -> None:
    matches = find_locations("디도 3층에서 학관으로 이동했어요.", LOCATIONS)

    assert {match.location.canonical_name for match in matches} == {"삼성학술정보관", "학생회관"}
    digital_library = next(match for match in matches if match.location.canonical_name == "삼성학술정보관")
    assert digital_library.matched_name == "디도"
    assert digital_library.resolved_name == "삼성학술정보관 3층"


def test_single_location_helper_rejects_ambiguous_or_unknown_queries() -> None:
    assert find_location("디도에서 잃어버렸어요.", LOCATIONS) == LOCATIONS[0]
    assert find_location("디도에서 학관으로 이동했어요.", LOCATIONS) is None
    assert find_location("등록되지 않은 장소", LOCATIONS) is None

