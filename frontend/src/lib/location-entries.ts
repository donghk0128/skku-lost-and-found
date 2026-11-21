import type { PickedLocation } from "@/lib/location-picker";

export type LocationEntry = { id: string; text: string; pin: PickedLocation | null };

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
