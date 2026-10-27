import { request } from "@/lib/auth-api";

export type AIDraft = {
  post_type: "LOST" | "FOUND";
  title: string;
  description: string;
  item_name: string | null;
  category_id: number;
  category_code: string;
  location_text: string | null;
  latitude: number | null;
  longitude: number | null;
  event_start_at: string | null;
  event_end_at: string | null;
  keywords: string[];
  missing_fields: string[];
  warnings: string[];
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
  ) => request<AIDraft>("/ai/post-drafts", body, token),
};
