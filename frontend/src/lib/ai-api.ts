import { File } from "expo-file-system";
import type { ImagePickerAsset } from "expo-image-picker";
import { Platform } from "react-native";

import { ApiError, baseUrl, request } from "@/lib/auth-api";
import { t } from "@/i18n";

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
  images_analyzed: boolean;
};

type AIImageAsset = Pick<ImagePickerAsset, "uri"> &
  Partial<Pick<ImagePickerAsset, "file" | "fileName" | "mimeType">>;

type AIChatBody = {
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
};

async function continueChatWithImages(
  body: AIChatBody,
  token: string,
  images: AIImageAsset[],
): Promise<AIChatResult> {
  const form = new FormData();
  form.append("payload", JSON.stringify(body));
  for (const image of images) {
    if (Platform.OS === "web") {
      const file = image.file ?? await (await fetch(image.uri)).blob();
      form.append("images", file, image.fileName ?? "photo.jpg");
    } else {
      form.append("images", new File(image.uri));
    }
  }
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 130000);
  try {
    const response = await fetch(`${baseUrl}/ai/post-draft-chat-with-images`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: form,
      signal: controller.signal,
    });
    const data = await response.json();
    if (!response.ok) {
      throw new ApiError(
        response.status,
        data?.error?.message ?? t("common.requestFailed"),
        data?.error?.code,
      );
    }
    return data as AIChatResult;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    if (error instanceof Error && error.name === "AbortError") {
      throw new Error(t("api.timeout"));
    }
    throw new Error(t("api.connectionFailed"));
  } finally {
    clearTimeout(timeout);
  }
}

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
    body: AIChatBody,
    token: string,
    images: AIImageAsset[] = [],
  ) => images.length
    ? continueChatWithImages(body, token, images)
    : request<AIChatResult>("/ai/post-draft-chat", body, token, undefined, 130000),
};
