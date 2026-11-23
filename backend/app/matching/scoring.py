"""Deterministic rule signals used alongside optional embedding similarity."""

from math import asin, cos, exp, radians, sin, sqrt
import re
import unicodedata
from dataclasses import dataclass

from app.posts.model import Post

TEXT_WEIGHT = 0.15
CATEGORY_WEIGHT = 0.25
TIME_WEIGHT = 0.30
LOCATION_WEIGHT = 0.30

# Compare explicit colors only when both posts describe the same part of an item.
_COLORS = {
    "black": r"검은색|검정색|검은|검정|까만|블랙|black",
    "white": r"흰색|하얀색|흰|하얀|화이트|white",
    "green": r"초록색|초록|녹색|그린|green",
    "blue": r"파란색|파란|파랑|푸른|청색|블루|blue",
    "red": r"빨간색|빨간|빨강|붉은|적색|레드|red",
    "yellow": r"노란색|노란|노랑|황색|옐로|yellow",
    "pink": r"분홍색|분홍|핑크|pink",
    "purple": r"보라색|보라|퍼플|purple",
    "gray": r"회색|그레이|gray|grey",
    "brown": r"갈색|브라운|brown",
}
_COLOR_WORDS = "|".join(f"(?P<{color}>{pattern})" for color, pattern in _COLORS.items())
_COLOR_COMPONENT = re.compile(
    rf"(?:{_COLOR_WORDS})\s*(?P<part>케이스|스티커|에어팟|이어폰|헤드폰|지갑|노트북|가방|모자|열쇠|우산|휴대폰|핸드폰|텀블러)",
    re.IGNORECASE,
)


@dataclass(frozen=True)
class RuleSignals:
    text: float
    category: float
    time: float
    location: float
    distance_km: float | None
    time_gap_hours: float | None
    color_conflict: bool = False

    @property
    def score(self) -> float:
        return (
            TEXT_WEIGHT * self.text
            + CATEGORY_WEIGHT * self.category
            + TIME_WEIGHT * self.time
            + LOCATION_WEIGHT * self.location
        )

    @property
    def ranking_score(self) -> float:
        """Do not count an unavailable coordinate pair as evidence of distance."""
        if self.distance_km is None:
            return self.score / (1 - LOCATION_WEIGHT)
        return self.score


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


def _explicit_colors(post: Post) -> dict[str, set[str]]:
    colors: dict[str, set[str]] = {}
    for match in _COLOR_COMPONENT.finditer(" ".join((post.title, post.item_name or "", post.description))):
        part = match.group("part")
        key = part if part in {"케이스", "스티커"} else "물건"
        color = next(name for name in _COLORS if match.group(name) is not None)
        colors.setdefault(key, set()).add(color)
    return colors


def _color_conflict(source: Post, candidate: Post) -> bool:
    source_colors, candidate_colors = _explicit_colors(source), _explicit_colors(candidate)
    return any(
        part in candidate_colors and source_values.isdisjoint(candidate_colors[part])
        for part, source_values in source_colors.items()
    )


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


def rule_signals(source: Post, candidate: Post) -> RuleSignals:
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

    return RuleSignals(
        text=text_score,
        category=category_score,
        time=time_score,
        location=location_score,
        distance_km=distance,
        time_gap_hours=time_gap,
        color_conflict=_color_conflict(source, candidate),
    )


def score_posts(source: Post, candidate: Post) -> float:
    """Return a ranking score in [0, 1], not a match probability."""
    return rule_signals(source, candidate).ranking_score
