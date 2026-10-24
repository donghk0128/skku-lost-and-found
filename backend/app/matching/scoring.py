"""Deterministic ranking signals; text scoring can later use embeddings."""

from math import asin, cos, exp, radians, sin, sqrt
import unicodedata

from app.posts.model import Post

TEXT_WEIGHT = 0.55
CATEGORY_WEIGHT = 0.20
TIME_WEIGHT = 0.15
LOCATION_WEIGHT = 0.10


def _compact(text: str) -> str:
    normalized = unicodedata.normalize("NFKC", text).casefold()
    return "".join(character for character in normalized if character.isalnum())


def _bigrams(text: str) -> set[str]:
    return {text[index : index + 2] for index in range(len(text) - 1)} if len(text) > 1 else {text}


def _text_similarity(left: str, right: str) -> float:
    left_parts, right_parts = _bigrams(_compact(left)), _bigrams(_compact(right))
    if not left_parts or not right_parts:
        return 0.0
    return 2 * len(left_parts & right_parts) / (len(left_parts) + len(right_parts))


def _distance_km(source: Post, candidate: Post) -> float | None:
    if (
        source.latitude is None
        or source.longitude is None
        or candidate.latitude is None
        or candidate.longitude is None
    ):
        return None
    source_lat, source_lon = radians(float(source.latitude)), radians(float(source.longitude))
    candidate_lat, candidate_lon = radians(float(candidate.latitude)), radians(float(candidate.longitude))
    latitude_difference = candidate_lat - source_lat
    longitude_difference = candidate_lon - source_lon
    arc = (
        sin(latitude_difference / 2) ** 2
        + cos(source_lat) * cos(candidate_lat) * sin(longitude_difference / 2) ** 2
    )
    return 6371.0088 * 2 * asin(min(1.0, sqrt(arc)))


def _time_gap_hours(source: Post, candidate: Post) -> float | None:
    if (
        source.event_start_at is None
        or source.event_end_at is None
        or candidate.event_start_at is None
        or candidate.event_end_at is None
    ):
        return None
    gap = max(source.event_start_at, candidate.event_start_at) - min(
        source.event_end_at, candidate.event_end_at
    )
    return max(0.0, gap.total_seconds() / 3600)


def score_posts(source: Post, candidate: Post) -> float:
    """Return a ranking score in [0, 1], not a match probability."""
    source_name = source.item_name or source.title
    candidate_name = candidate.item_name or candidate.title
    source_text = " ".join((source.title, source.item_name or "", source.description))
    candidate_text = " ".join((candidate.title, candidate.item_name or "", candidate.description))
    text_score = 0.7 * _text_similarity(source_name, candidate_name) + 0.3 * _text_similarity(
        source_text, candidate_text
    )

    category_score = float(source.category_id is not None and source.category_id == candidate.category_id)
    distance = _distance_km(source, candidate)
    location_score = exp(-distance / 3) if distance is not None else 0.0
    time_gap = _time_gap_hours(source, candidate)
    time_score = exp(-time_gap / 48) if time_gap is not None else 0.0

    return (
        TEXT_WEIGHT * text_score
        + CATEGORY_WEIGHT * category_score
        + TIME_WEIGHT * time_score
        + LOCATION_WEIGHT * location_score
    )
