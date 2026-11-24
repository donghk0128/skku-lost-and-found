import type { PickedLocation } from "@/lib/location-picker";

export type LocationEntry = { id: string; text: string; pin: PickedLocation | null };

export type PostLocationInput = {
  location_text: string | null;
  latitude: number | null;
  longitude: number | null;
};

/** Empty UI placeholders are not locations; preserve every other row in order. */
export function locationEntriesToPayload(entries: LocationEntry[]): PostLocationInput[] {
  return entries.filter(row => row.text.trim() || row.pin).map(row => ({
    location_text: row.text.trim() || null,
    latitude: row.pin ? Number(row.pin.latitude.toFixed(6)) : null,
    longitude: row.pin ? Number(row.pin.longitude.toFixed(6)) : null,
  }));
}

/** An empty array is authoritative; fall back only for a legacy API response. */
export function locationEntriesFromPost(post: {
  locations?: PostLocationInput[];
  location_text: string | null;
  latitude: number | null;
  longitude: number | null;
}): LocationEntry[] {
  const locations = post.locations ?? (
    post.location_text !== null || post.latitude !== null ? [post] : []
  );
  return locations.map((location, index) => ({
    id: `saved-location-${index}`,
    text: location.location_text ?? "",
    pin: location.latitude !== null && location.longitude !== null ? {
      address: location.location_text ?? "",
      latitude: location.latitude,
      longitude: location.longitude,
    } : null,
  }));
}

/** Commas and newlines are optional shortcuts; candidate alternatives are not split. */
export function locationEntriesFromText(text: string): LocationEntry[] {
  const names = [...new Set(text.split(/[,，\n]+/).map(name => name.trim()).filter(Boolean))];
  return (names.length ? names : [""]).map((name, index) => ({ id: `location-${index}`, text: name.slice(0, 255), pin: null }));
}

/** Read frontend-only drafts when moving from AI chat to the manual editor. */
export function parseLocationEntries(serialized?: string): LocationEntry[] {
  if (!serialized) return [];
  try {
    const data: unknown = JSON.parse(serialized);
    if (!Array.isArray(data)) return [];
    return data.filter((row): row is Record<string, unknown> => Boolean(row) && typeof row === "object" && typeof row.text === "string").map((row, index) => {
      const value = row.pin;
      let pin: PickedLocation | null = null;
      if (value && typeof value === "object" && "latitude" in value && "longitude" in value && "address" in value
        && typeof value.latitude === "number" && Number.isFinite(value.latitude) && Math.abs(value.latitude) <= 90
        && typeof value.longitude === "number" && Number.isFinite(value.longitude) && Math.abs(value.longitude) <= 180
        && typeof value.address === "string") {
        pin = { address: value.address, latitude: value.latitude, longitude: value.longitude };
      }
      return { id: `restored-${index}`, text: String(row.text).slice(0, 255), pin };
    });
  } catch { return []; }
}
