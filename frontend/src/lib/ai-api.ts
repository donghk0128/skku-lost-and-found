import { request } from "@/lib/auth-api";

export type AIDraft = {
  post_type: "LOST" | "FOUND";
  title: string;
  description: string;
  item_name: string | null;
  category_id: number;
  category_code: string;
  location_text: string | null;
  location_candidates: string[];
  latitude: number | null;
  longitude: number | null;
  event_start_at: string | null;
  event_end_at: string | null;
  time_precision: "DATE_ONLY" | "EXACT" | "APPROXIMATE" | "RANGE" | null;
  keywords: string[];
  missing_fields: string[];
  warnings: string[];
};

export type AIChatResult = {
  status: "NEEDS_INPUT" | "READY";
  assistant_message: string;
  draft: AIDraft;
  pending_field: "item_name" | "location" | "event_time" | null;
  collected_fields: Partial<Record<"item_name" | "location" | "event_time", string>>;
};

export const aiApi = {
  createDraft: (
    body: {
      post_type: "LOST" | "FOUND";
      natural_language: string;
      confirmed_location?: {
        text: string;
        latitude: number;
        longitude: number;
      };
      confirmed_event_start_at?: string;
      confirmed_event_end_at?: string;
    },
    token: string,
  ) => request<AIDraft>("/ai/post-drafts", body, token, undefined, 130000),
  continueChat: (
    body: {
      post_type: "LOST" | "FOUND";
      messages: { role: "user"; content: string }[];
      draft?: AIDraft;
      pending_field?: "item_name" | "location" | "event_time" | null;
      collected_fields?: Partial<Record<"item_name" | "location" | "event_time", string>>;
    },
    token: string,
  ) => request<AIChatResult>("/ai/post-draft-chat", body, token, undefined, 130000),
};
