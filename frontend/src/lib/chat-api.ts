import { Platform } from "react-native";
import { File } from "expo-file-system";
import type { ImagePickerAsset } from "expo-image-picker";
import { ApiError, authApi, baseUrl, request } from "@/lib/auth-api";
import { readSession, writeSession } from "@/lib/session-storage";
import { t } from "@/i18n";

export type ChatMessageImage = { id: string; position: number; content_type: string; image_url: string };
export type ChatMessage = {
  id: string; room_id: string; sender_id: string | null; sequence: number;
  message_type: "TEXT" | "IMAGE"; content: string | null;
  image_url: string | null; created_at: string;
  images: ChatMessageImage[]; client_message_id: string | null;
};
export type ChatRoom = {
  id: string; post_id: string | null; owner_id: string | null; requester_id: string | null;
  post_title: string; other_nickname: string;
  post_deleted: boolean; other_withdrawn: boolean;
  status: "ACTIVE" | "CLOSED";
  close_reason: "RETURNED" | "GENERAL" | "POST_COMPLETED" | null;
  closed_at: string | null; is_hidden: boolean; unread_count: number;
  last_read_sequence: number; last_message: ChatMessage | null;
  return_pair: { id: string; lost_post_id: string; found_post_id: string;
    counterpart_post_title: string;
    proposed_by_id: string; status: "PENDING" | "CONFIRMED"; confirmed_at: string | null } | null;
};
export type PairCandidate = { id: string; title: string; post_type: "LOST" | "FOUND" };

let refreshing: Promise<string> | null = null;
export async function chatToken(refresh = false): Promise<string> {
  const session = await readSession();
  if (!session) throw new Error(t("common.loginRequired"));
  if (!refresh) return session.access_token;
  if (!refreshing) {
    refreshing = (async () => {
      const result = await authApi.refresh(session.refresh_token);
      const current = await readSession();
      if (current?.refresh_token !== session.refresh_token) throw new Error(t("common.loginRequired"));
      await writeSession({ ...session, access_token: result.access_token });
      return result.access_token;
    })().finally(() => { refreshing = null; });
  }
  return refreshing;
}

export async function withChatToken<T>(action: (token: string) => Promise<T>): Promise<T> {
  try { return await action(await chatToken()); }
  catch (error) {
    if (!(error instanceof ApiError) || error.status !== 401) throw error;
    return action(await chatToken(true));
  }
}

const root = "/chat/rooms";
export const chatApi = {
  create: (post_id: string) => withChatToken(token => request<ChatRoom>(root, { post_id }, token)),
  rooms: (offset = 0, includeHidden = false) => withChatToken(token => request<{ items: ChatRoom[]; total: number }>(`${root}?offset=${offset}&limit=30&include_hidden=${includeHidden}`, undefined, token)),
  room: (id: string) => withChatToken(token => request<ChatRoom>(`${root}/${id}`, undefined, token)),
  messages: (id: string, after = 0) => withChatToken(token => request<{ items: ChatMessage[]; next_after: number; has_more: boolean }>(`${root}/${id}/messages?after=${after}&limit=100`, undefined, token)),
  send: (id: string, content: string, clientMessageId: string) => withChatToken(token => request<ChatMessage>(`${root}/${id}/messages`, { content, client_message_id: clientMessageId }, token)),
  read: (id: string, sequence: number) => withChatToken(token => request<ChatRoom>(`${root}/${id}/read`, { sequence }, token, "PATCH")),
  close: (id: string, reason: "RETURNED" | "GENERAL") => withChatToken(token => request<ChatRoom>(`${root}/${id}/close`, { reason }, token)),
  pairCandidates: (id: string) => withChatToken(token => request<PairCandidate[]>(`${root}/${id}/pair-candidates`, undefined, token)),
  proposePair: (id: string, counterpart_post_id: string) => withChatToken(token => request<ChatRoom>(`${root}/${id}/return-pair`, { counterpart_post_id }, token)),
  confirmPair: (id: string) => withChatToken(token => request<ChatRoom>(`${root}/${id}/return-pair/confirm`, {}, token)),
  rejectPair: (id: string) => withChatToken(token => request<ChatRoom>(`${root}/${id}/return-pair/reject`, {}, token)),
  hide: (id: string, is_hidden: boolean) => withChatToken(token => request<ChatRoom>(`${root}/${id}/visibility`, { is_hidden }, token, "PATCH")),
  images: (id: string, assets: ImagePickerAsset[], content: string, clientMessageId: string) => withChatToken(async token => {
    const form = new FormData();
    for (const asset of assets) {
      if (Platform.OS === "web") form.append("files", asset.file ?? await (await fetch(asset.uri)).blob(), asset.fileName ?? "photo.jpg");
      else form.append("files", new File(asset.uri));
    }
    if (content) form.append("content", content);
    form.append("client_message_id", clientMessageId);
    const controller = new AbortController();
    const timeout = setTimeout(() => controller.abort(), 120000);
    try {
      const response = await fetch(`${baseUrl}${root}/${id}/images`, {
        method: "POST", headers: { Authorization: `Bearer ${token}` }, body: form, signal: controller.signal,
      });
      const data = await response.json();
      if (!response.ok) throw new ApiError(response.status, data?.error?.message ?? t("api.photoUploadFailed"));
      return data as ChatMessage;
    } finally { clearTimeout(timeout); }
  }),
};

export function chatSocketUrl(id: string, after: number) {
  return `${baseUrl.replace(/^http/, "ws")}${root}/${id}/ws?after=${after}`;
}
