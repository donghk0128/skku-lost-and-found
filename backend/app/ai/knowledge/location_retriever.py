"""Load and search curated campus location aliases in user sentences."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path


DATA_PATH = Path(__file__).with_name("campus_locations.json")
FLOOR_PATTERN = re.compile(r"^\s*((?:지하\s*)?\d+\s*층|B\s*\d+\s*층?)", re.IGNORECASE)
CAMPUS_HINTS = {
    "HSSC": (
        "인문사회과학캠퍼스", "인사", "명륜캠퍼스", "명륜", "서울", "서울 캠퍼스", "혜화",
        "humanities and social sciences campus", "humanities campus", "seoul campus",
    ),
    "NSC": (
        "자연과학캠퍼스", "자과", "율전캠퍼스", "율전", "수원 캠퍼스", "수원",
        "natural sciences campus", "natural science campus", "suwon campus",
    ),
}


@dataclass(frozen=True)
class CampusLocation:
    """One canonical campus location and its accepted aliases."""

    canonical_name: str
    aliases: tuple[str, ...]
    location_id: str | None = None
    campus: str | None = None
    building_number: str | None = None
    localized_names: dict[str, str] | None = None
    localized_aliases: dict[str, tuple[str, ...]] | None = None

    def display_name(self, locale: str) -> str:
        """Return the localized display name with Korean as the fallback."""

        if not self.localized_names:
            return self.canonical_name
        return (
            self.localized_names.get(locale)
            or self.localized_names.get("ko")
            or self.canonical_name
        )

    def search_names(self, locale: str) -> tuple[str, ...]:
        """Search the requested locale first, then accept every other locale."""

        if not self.localized_names or not self.localized_aliases:
            return (self.canonical_name, *self.aliases)
        locale_names = (
            self.localized_names.get(locale),
            *self.localized_aliases.get(locale, ()),
        )
        fallback_names = tuple(self.localized_names.values()) + tuple(
            alias
            for aliases in self.localized_aliases.values()
            for alias in aliases
        )
        return tuple(dict.fromkeys(name for name in (*locale_names, *fallback_names) if name))


@dataclass(frozen=True)
class LocationMatch:
    """One sentence match with the alias and adjacent floor preserved."""

    location: CampusLocation
    matched_name: str
    floor: str | None = None
    locale: str = "ko"
    position: int = 0

    @property
    def resolved_name(self) -> str:
        """Return the canonical name with an explicitly supplied floor."""

        canonical_name = self.location.display_name(self.locale)
        return f"{canonical_name} {self.floor}" if self.floor else canonical_name


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(character for character in normalized if character.isalnum())


def load_locations(path: Path = DATA_PATH) -> tuple[CampusLocation, ...]:
    """Load validated location entries from the curated JSON file."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    locations: list[CampusLocation] = []
    for entry in payload["locations"]:
        names = entry["names"]
        aliases = {
            locale: tuple(values)
            for locale, values in entry.get("aliases", {}).items()
        }
        locations.append(
            CampusLocation(
                canonical_name=names.get("ko") or next(iter(names.values())),
                aliases=tuple(dict.fromkeys(alias for values in aliases.values() for alias in values)),
                location_id=entry["id"],
                campus=entry.get("campus"),
                building_number=entry.get("building_number"),
                localized_names=names,
                localized_aliases=aliases,
            )
        )
    return tuple(locations)


def _floor_after(query: str, name: str) -> str | None:
    normalized_query = unicodedata.normalize("NFKC", query)
    normalized_name = unicodedata.normalize("NFKC", name)
    match = re.search(re.escape(normalized_name), normalized_query, re.IGNORECASE)
    if match is None:
        return None
    floor_match = FLOOR_PATTERN.match(normalized_query[match.end() :])
    return re.sub(r"\s+", "", floor_match.group(1)) if floor_match else None


def find_locations(
    query: str,
    locations: tuple[CampusLocation, ...] | None = None,
    locale: str = "ko",
) -> tuple[LocationMatch, ...]:
    """Return every distinct location mentioned in a sentence, longest aliases first."""

    normalized_query = _normalize(query)
    if not normalized_query:
        return ()
    candidates = locations if locations is not None else load_locations()
    mentioned_campuses = {
        campus
        for campus, hints in CAMPUS_HINTS.items()
        if any(_normalize(hint) in normalized_query for hint in hints)
    }
    if len(mentioned_campuses) == 1:
        campus = next(iter(mentioned_campuses))
        candidates = tuple(
            location for location in candidates
            if location.campus is None or location.campus == campus
        )

    matches: dict[str, tuple[LocationMatch, int, int]] = {}
    for location in candidates:
        names = sorted(
            location.search_names(locale),
            key=lambda value: len(_normalize(value)),
            reverse=True,
        )
        for name in names:
            normalized_name = _normalize(name)
            if len(normalized_name) < 2 or normalized_name not in normalized_query:
                continue
            position = normalized_query.find(normalized_name)
            match_key = location.location_id or location.canonical_name
            current = matches.get(match_key)
            if current is None or len(normalized_name) > current[2] - current[1]:
                matches[match_key] = (
                    LocationMatch(
                        location=location,
                        matched_name=name,
                        floor=_floor_after(query, name),
                        locale=locale,
                        position=position,
                    ),
                    position,
                    position + len(normalized_name),
                )

    match_values = list(matches.values())
    if not mentioned_campuses:
        by_span: dict[tuple[int, int], list[tuple[LocationMatch, int, int]]] = {}
        for value in match_values:
            by_span.setdefault((value[1], value[2]), []).append(value)
        inferred_campuses = {
            group[0][0].location.campus
            for group in by_span.values()
            if len(group) == 1 and group[0][0].location.campus is not None
        }
        if len(inferred_campuses) == 1:
            inferred_campus = next(iter(inferred_campuses))
            match_values = [
                value
                for value in match_values
                if len(by_span[(value[1], value[2])]) == 1
                or value[0].location.campus == inferred_campus
            ]

    # Prefer a more specific name at the same text span. This prevents, for
    # example, "수선관" from also matching inside "수선관 별관".
    distinct: list[tuple[LocationMatch, int, int]] = []
    for candidate in sorted(match_values, key=lambda value: (value[1], -(value[2] - value[1]))):
        _, start, end = candidate
        if any(
            start >= kept_start
            and end <= kept_end
            and (start, end) != (kept_start, kept_end)
            for _, kept_start, kept_end in distinct
        ):
            continue
        distinct.append(candidate)
    return tuple(match for match, _, _ in sorted(distinct, key=lambda value: value[1]))


def find_location(
    query: str,
    locations: tuple[CampusLocation, ...] | None = None,
    locale: str = "ko",
) -> CampusLocation | None:
    """Return a location only when the sentence has exactly one distinct candidate."""

    matches = find_locations(query, locations, locale)
    return matches[0].location if len(matches) == 1 else None
