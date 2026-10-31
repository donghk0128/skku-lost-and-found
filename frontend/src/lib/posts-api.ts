import { Platform } from "react-native";
import { File } from "expo-file-system";
import type { ImagePickerAsset } from "expo-image-picker";
import { baseUrl, request, ApiError } from "@/lib/auth-api";

export type Post = {
  id: string;
  author_id: string;
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
  latitude?: number;
  longitude?: number;
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
  upload: async (id: string, asset: ImagePickerAsset, token: string) => {
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
        data?.error?.message ?? "사진 업로드에 실패했습니다.",
      );
    }
  },
  list: (type: "LOST" | "FOUND", search: string, offset: number) => {
    const query = new URLSearchParams({
      post_type: type,
      limit: "20",
      offset: String(offset),
    });
    if (search.trim()) query.set("q", search.trim());
    return request<{ items: Post[]; total: number }>(`/posts?${query}`);
  },
  categories: () => request<Category[]>("/categories"),
  images: (id: string) =>
    request<{ content_url: string }[]>(`/posts/${id}/images`),
};
export function imageUrl(path: string) {
  return new URL(path, `${baseUrl}/`).toString();
}
