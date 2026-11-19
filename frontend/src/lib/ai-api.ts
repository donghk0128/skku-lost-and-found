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
  location_options: LocationOption[];
  selected_location_ids: string[];
  latitude: number | null;
  longitude: number | null;
  event_start_at: string | null;
  event_end_at: string | null;
  time_precision: "DATE_ONLY" | "EXACT" | "APPROXIMATE" | "RANGE" | null;
  keywords: string[];
  missing_fields: string[];
  warnings: string[];
};

export type LocationOption = {
  id: string;
  campus: string | null;
  name: string;
  label: string;
};

export type AIRequiredFields = {
  item_name: string | null;
  location_text: string | null;
  location_candidates: string[];
  location_options: LocationOption[];
  selected_location_ids: string[];
  event_start_at: string | null;
  event_end_at: string | null;
  time_precision: "DATE_ONLY" | "EXACT" | "APPROXIMATE" | "RANGE" | null;
  missing_fields: ("item_name" | "location" | "event_time")[];
};

export type PendingField =
  | "item_name"
  | "location"
  | "location_selection"
  | "event_time"
  | null;

export type AIChatResult = {
  status: "NEEDS_INPUT" | "READY";
  assistant_message: string;
  draft: AIDraft | null;
  required_fields: AIRequiredFields;
  pending_field: PendingField;
  collected_fields: Partial<Record<"item_name" | "location" | "event_time", string>>;
  selected_location_ids: string[];
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
      locale: "ko" | "en";
      post_type: "LOST" | "FOUND";
      messages: { role: "user"; content: string }[];
      draft?: AIDraft;
      required_fields?: AIRequiredFields;
      pending_field?: PendingField;
      collected_fields?: Partial<Record<"item_name" | "location" | "event_time", string>>;
      selected_location_ids?: string[];
      confirmed_location?: {
        text: string;
        latitude: number;
        longitude: number;
      };
    },
    token: string,
  ) => request<AIChatResult>("/ai/post-draft-chat", body, token, undefined, 130000),
};
