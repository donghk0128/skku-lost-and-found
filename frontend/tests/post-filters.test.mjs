import assert from "node:assert/strict";
import test from "node:test";
import { emptyPostFilters, hasPostFilters, normalizePostFilters, postFiltersQuery } from "../src/lib/post-filters.ts";

test("search remains one phrase and OR elements remain repeated parameters", () => {
  const value = { ...emptyPostFilters(), q: " 검정 에어팟 ", category_id: 1,
    title_terms: ["혹시", "저기"], location_terms: ["디도 뒷문", "학생회관"], event_at: "2026-11-24T10:00:00.000Z" };
  const query = postFiltersQuery(value);
  assert.deepEqual(query.getAll("q"), ["검정 에어팟"]);
  assert.deepEqual(query.getAll("title_terms"), ["혹시", "저기"]);
  assert.deepEqual(query.getAll("location_terms"), ["디도 뒷문", "학생회관"]);
  assert.equal(query.get("event_at"), value.event_at);
  assert.equal(query.get("category_id"), "1");
});

test("clearing search preserves the other types, and empty filters send no constraints", () => {
  const value = { ...emptyPostFilters(), title_terms: ["혹시"], q: " " };
  assert.equal(postFiltersQuery(value).has("q"), false);
  assert.deepEqual(postFiltersQuery(value).getAll("title_terms"), ["혹시"]);
  assert.equal(hasPostFilters(value), true);
  assert.equal(hasPostFilters(emptyPostFilters()), false);
  assert.equal(postFiltersQuery(emptyPostFilters()).toString(), "");
});

test("normalization drops empty entries and case duplicates without splitting spaces or mutating a snapshot", () => {
  const value = { ...emptyPostFilters(), title_terms: [" AirPods Pro ", "airpods pro", "AirPods  Pro", " "] };
  const normalized = normalizePostFilters(value);
  assert.deepEqual(normalized.title_terms, ["AirPods Pro", "AirPods  Pro"]);
  assert.equal(value.title_terms.length, 4);
  normalized.title_terms.push("new");
  assert.equal(value.title_terms.length, 4);
});
