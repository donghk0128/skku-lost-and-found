export type PostFilters = {
  q: string | null;
  category_id: number | null;
  title_terms: string[];
  content_terms: string[];
  location_terms: string[];
  event_at: string | null;
};

export const MAX_FILTER_TERMS = 20;
export const emptyPostFilters = (): PostFilters => ({
  q: null, category_id: null, title_terms: [], content_terms: [], location_terms: [], event_at: null,
});

export function uniquePhrases(values: string[]): string[] {
  const seen = new Set<string>();
  return values.map(value => value.trim()).filter(value => {
    const key = value.toLowerCase();
    if (!value || seen.has(key)) return false;
    seen.add(key);
    return true;
  });
}

export function normalizePostFilters(value: PostFilters): PostFilters {
  return {
    q: value.q?.trim() || null, category_id: value.category_id,
    title_terms: uniquePhrases(value.title_terms), content_terms: uniquePhrases(value.content_terms),
    location_terms: uniquePhrases(value.location_terms), event_at: value.event_at,
  };
}

export function hasPostFilters(value: PostFilters): boolean {
  return Boolean(value.q?.trim() || value.category_id !== null || value.title_terms.length
    || value.content_terms.length || value.location_terms.length || value.event_at);
}

export function postFiltersQuery(value: PostFilters): URLSearchParams {
  const filters = normalizePostFilters(value);
  const query = new URLSearchParams();
  if (filters.q) query.set("q", filters.q);
  if (filters.category_id !== null) query.set("category_id", String(filters.category_id));
  for (const field of ["title_terms", "content_terms", "location_terms"] as const) {
    filters[field].forEach(term => query.append(field, term));
  }
  if (filters.event_at) query.set("event_at", filters.event_at);
  return query;
}
