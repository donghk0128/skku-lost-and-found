"""Load and search curated campus location aliases in user sentences."""

from __future__ import annotations

import json
import re
import unicodedata
from dataclasses import dataclass
from pathlib import Path


DATA_PATH = Path(__file__).with_name("campus_locations.json")
FLOOR_PATTERN = re.compile(r"^\s*((?:지하\s*)?\d+\s*층|B\s*\d+\s*층?)", re.IGNORECASE)


@dataclass(frozen=True)
class CampusLocation:
    """One canonical campus location and its accepted aliases."""

    canonical_name: str
    aliases: tuple[str, ...]


@dataclass(frozen=True)
class LocationMatch:
    """One sentence match with the alias and adjacent floor preserved."""

    location: CampusLocation
    matched_name: str
    floor: str | None = None

    @property
    def resolved_name(self) -> str:
        """Return the canonical name with an explicitly supplied floor."""

        return f"{self.location.canonical_name} {self.floor}" if self.floor else self.location.canonical_name


def _normalize(value: str) -> str:
    normalized = unicodedata.normalize("NFKC", value).casefold()
    return "".join(character for character in normalized if character.isalnum())


def load_locations(path: Path = DATA_PATH) -> tuple[CampusLocation, ...]:
    """Load validated location entries from the curated JSON file."""

    payload = json.loads(path.read_text(encoding="utf-8"))
    return tuple(
        CampusLocation(
            canonical_name=entry["canonical_name"],
            aliases=tuple(entry.get("aliases", [])),
        )
        for entry in payload["locations"]
    )


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
) -> tuple[LocationMatch, ...]:
    """Return every distinct location mentioned in a sentence, longest aliases first."""

    normalized_query = _normalize(query)
    if not normalized_query:
        return ()
    candidates = locations if locations is not None else load_locations()
    matches: dict[str, LocationMatch] = {}
    for location in candidates:
        names = sorted(
            (location.canonical_name, *location.aliases),
            key=lambda value: len(_normalize(value)),
            reverse=True,
        )
        for name in names:
            normalized_name = _normalize(name)
            if len(normalized_name) < 2 or normalized_name not in normalized_query:
                continue
            current = matches.get(location.canonical_name)
            if current is None or len(normalized_name) > len(_normalize(current.matched_name)):
                matches[location.canonical_name] = LocationMatch(
                    location=location,
                    matched_name=name,
                    floor=_floor_after(query, name),
                )
    return tuple(
        sorted(matches.values(), key=lambda match: len(_normalize(match.matched_name)), reverse=True)
    )


def find_location(query: str, locations: tuple[CampusLocation, ...] | None = None) -> CampusLocation | None:
    """Return a location only when the sentence has exactly one distinct candidate."""

    matches = find_locations(query, locations)
    return matches[0].location if len(matches) == 1 else None

