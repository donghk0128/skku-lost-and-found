from app.ai.knowledge.location_retriever import find_locations


def test_dormitory_alias_resolves_to_canonical_name():
    matches = find_locations("인관에서 잃어버렸어요")

    assert [match.resolved_name for match in matches] == ["인관"]
