import assert from "node:assert/strict";
import test from "node:test";
import { locationEntriesFromPost, locationEntriesToPayload } from "../src/lib/location-entries.ts";

const entries = [
  { id: "primary", text: "학생회관", pin: { address: "서울", latitude: 37.588, longitude: 126.993 } },
  { id: "second", text: "도서관", pin: { address: "수원", latitude: 37.2939, longitude: 126.9751 } },
  { id: "text-only", text: "버스 정류장", pin: null },
  { id: "coordinates-only", text: "", pin: { address: "", latitude: 0, longitude: 0 } },
];

test("all locations retain their order, text and coordinate pairs after a save/read roundtrip", () => {
  const payload = locationEntriesToPayload(entries);
  assert.equal(payload.length, entries.length);
  const response = {
    ...payload[0],
    locations: payload.map((location, position) => ({ ...location, position })),
  };
  const restored = locationEntriesFromPost(response);
  assert.deepEqual(restored.map(row => row.text), entries.map(row => row.text));
  assert.deepEqual(locationEntriesToPayload(restored), payload);
  assert.equal(response.latitude, entries[0].pin.latitude);
});

test("empty placeholders yield zero locations; duplicate locations remain separate", () => {
  assert.deepEqual(locationEntriesToPayload([{ id: "blank", text: "  ", pin: null }]), []);
  assert.equal(locationEntriesToPayload([entries[0], entries[0]]).length, 2);
});

test("no stored location is truncated, including lists above today's limit", () => {
  const payload = locationEntriesToPayload(Array.from({ length: 25 }, (_, i) => ({
    id: String(i), text: `장소 ${i}`, pin: null,
  })));
  assert.equal(locationEntriesFromPost({ location_text: null, latitude: null, longitude: null, locations: payload }).length, 25);
});

test("a text-only first location stays first even when later locations have coordinates", () => {
  const payload = locationEntriesToPayload([entries[2], entries[1]]);
  const restored = locationEntriesFromPost({ ...payload[0], locations: payload });
  assert.equal(restored[0].pin, null);
  assert.equal(restored[1].pin.latitude, entries[1].pin.latitude);
});

test("an explicit empty list overrides legacy fields; old responses still restore one location", () => {
  const legacy = { location_text: "구형 게시물", latitude: 37.5, longitude: 127 };
  assert.equal(locationEntriesFromPost(legacy).length, 1);
  assert.deepEqual(locationEntriesFromPost({ ...legacy, locations: [] }), []);
});

test("coordinates use the API's existing six-decimal precision", () => {
  const [location] = locationEntriesToPayload([
    { id: "pin", text: "장소", pin: { address: "", latitude: 37.12345678, longitude: 126.12345678 } },
  ]);
  assert.equal(location.latitude, 37.123457);
  assert.equal(location.longitude, 126.123457);
});
