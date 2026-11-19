"""Build user-selectable locations from campus-directory matches."""

from app.ai.knowledge.location_retriever import LocationMatch
from app.ai.schemas import Locale, LocationOption


def build_location_options(
    matches: tuple[LocationMatch, ...], locale: Locale
) -> list[LocationOption]:
    names = [match.resolved_name for match in matches]
    duplicate_names = {name for name in names if names.count(name) > 1}
    campus_labels = (
        {"HSSC": "Humanities and Social Sciences Campus", "NSC": "Natural Sciences Campus"}
        if locale == "en"
        else {"HSSC": "인문사회과학캠퍼스", "NSC": "자연과학캠퍼스"}
    )
    return [
        LocationOption(
            id=match.location.location_id,
            campus=match.location.campus,
            name=match.resolved_name,
            label=(
                f"{campus_labels[match.location.campus]} {match.resolved_name}"
                if match.resolved_name in duplicate_names
                and match.location.campus in campus_labels
                else match.resolved_name
            ),
        )
        for match in matches
        if match.location.location_id is not None
    ]
