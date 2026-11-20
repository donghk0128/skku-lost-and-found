import { Platform } from "react-native";
import { File } from "expo-file-system";
import type { ImagePickerAsset } from "expo-image-picker";
import { baseUrl, request, ApiError } from "@/lib/auth-api";
import { t } from "@/i18n";

export type Post = {
  id: string;
  author_id: string;
  /** Optional while a client is connected to a pre-nickname backend deployment. */
  author_nickname?: string;
  post_type: "LOST" | "FOUND";
  title: string;
  description: string;
  category_id: number | null;
  status: "OPEN" | "COMPLETED";
  created_at: string;
  item_name: string | null;
  location_text: string | null;
  latitude: number | null;
  longitude: number | null;
  event_start_at: string | null;
  event_end_at: string | null;
};
export type Category = { id: number; name: string; code: string };
export type RecommendationReason =
  | "NEARBY_LOCATION"
  | "OVERLAPPING_TIME"
  | "SAME_CATEGORY"
  | "SIMILAR_MEANING";
export type RankedCandidate = {
  post: Post;
  rank: number;
  score: number;
  rule_score: number;
  semantic_score: number | null;
  reasons: RecommendationReason[];
};
export type PostImageAsset = Pick<ImagePickerAsset, "uri"> &
  Partial<
    Pick<ImagePickerAsset, "file" | "fileName" | "fileSize" | "mimeType">
  >;
export type CreatePost = {
  post_type: "LOST" | "FOUND";
  title: string;
  description: string;
  category_id?: number;
  location_text?: string;
  item_name?: string;
  event_start_at?: string;
  event_end_at?: string;
  latitude?: number;
  longitude?: number;
};
export type UpdatePost = {
  title: string;
  description: string;
  category_id: number | null;
  location_text: string | null;
  event_start_at: string | null;
  event_end_at: string | null;
  latitude?: number | null;
  longitude?: number | null;
};
export const postsApi = {
  update: (id: string, body: UpdatePost, token: string) =>
    request<Post>(`/posts/${id}`, body, token, "PATCH"),
  delete: (id: string, token: string) =>
    request<void>(`/posts/${id}`, undefined, token, "DELETE"),
  detail: (id: string) => request<Post>(`/posts/${id}`),
  recommendations: (id: string) =>
    request<{ items: { post: Post; score: number }[] }>(
      `/posts/${id}/recommendations?limit=5`,
    ),
  create: (body: CreatePost, token: string) =>
    request<Post>("/posts", body, token),
  createAiAssisted: (body: CreatePost, token: string) =>
    request<Post>("/posts/ai-assisted", body, token),
  upload: async (id: string, asset: PostImageAsset, token: string) => {
    const form = new FormData();
    if (Platform.OS === "web") {
      const file = asset.file ?? (await (await fetch(asset.uri)).blob());
      form.append("file", file, asset.fileName ?? "photo.jpg");
    } else {
      // Expo File implements bytes(), which SDK 57 fetch reads directly.
      // Do not construct an RN Blob from ArrayBuffer: iOS does not support it.
      form.append("file", new File(asset.uri));
    }
    const response = await fetch(`${baseUrl}/posts/${id}/images`, {
      method: "POST",
      headers: { Authorization: `Bearer ${token}` },
      body: form,
    });
    if (!response.ok) {
      const data = await response.json().catch(() => null);
      throw new ApiError(
        response.status,
        data?.error?.message ?? t("api.photoUploadFailed"),
      );
    }
  },
  list: (
    type: "LOST" | "FOUND",
    search: string,
    offset: number,
    categoryId: number | null = null,
  ) => {
    const query = new URLSearchParams({
      post_type: type,
      limit: "20",
      offset: String(offset),
    });
    if (search.trim()) query.set("q", search.trim());
    if (categoryId !== null) query.set("category_id", String(categoryId));
    return request<{ items: Post[]; total: number }>(`/posts?${query}`);
  },
  mine: (type: "LOST" | "FOUND", token: string) =>
    request<{ items: Post[]; total: number }>(
      `/posts/mine?post_type=${type}&limit=100`,
      undefined,
      token,
    ),
  rankedCandidates: (
    sourcePostId: string,
    search: string,
    categoryId: number | null,
    offset: number,
    token: string,
  ) => {
    const query = new URLSearchParams({ limit: "20", offset: String(offset) });
    if (search.trim()) query.set("q", search.trim());
    if (categoryId !== null) query.set("category_id", String(categoryId));
    return request<{
      source_post_id: string;
      run_id: string;
      algorithm_version: string;
      items: RankedCandidate[];
      total: number;
    }>(`/posts/${sourcePostId}/ranked-candidates?${query}`, undefined, token);
  },
  categories: () => request<Category[]>("/categories"),
  images: (id: string) =>
    request<{ content_url: string }[]>(`/posts/${id}/images`),
};
export function imageUrl(path: string) {
  return new URL(path, `${baseUrl}/`).toString();
}
