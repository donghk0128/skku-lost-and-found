// Small best-effort client for authenticated service usage events.

import * as Crypto from "expo-crypto";
import { request } from "@/lib/auth-api";
import { withChatToken } from "@/lib/chat-api";

export type ClientEvent = {
  event_type: "screen_view" | "post_view" | "search_applied" | "filter_applied" | "recommendation_impression" | "recommendation_click";
  visit_id?: string;
  screen?: "home" | "post_detail" | "chat" | "my_posts" | "create_post";
  post_id?: string;
  source_post_id?: string;
  candidate_post_id?: string;
  run_id?: string;
  rank?: number;
  category_id?: number;
  has_query?: boolean;
  has_title_terms?: boolean;
  has_content_terms?: boolean;
  has_location_terms?: boolean;
  has_event_time?: boolean;
};

export const newVisitId = () => Crypto.randomUUID();

export function trackEvent(event: ClientEvent): void {
  try {
    const body = { ...event, event_id: Crypto.randomUUID(), occurred_at: new Date().toISOString() };
    // withChatToken may repeat after a refresh; body keeps its original event_id.
    void withChatToken(token => request("/events", body, token)).catch(() => undefined);
  } catch {
    // Analytics must not interrupt navigation or an existing user action.
  }
}
