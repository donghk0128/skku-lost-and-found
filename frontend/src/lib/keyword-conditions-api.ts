import { request } from "@/lib/auth-api";
import { withChatToken } from "@/lib/chat-api";
import { normalizePostFilters, type PostFilters } from "@/lib/post-filters";

export type KeywordCondition = {
  id: string;
  post_type: "LOST" | "FOUND";
  version: number;
  conditions: PostFilters;
  created_at: string;
  notification_enabled: boolean;
};
export type KeywordConditionPage = { items: KeywordCondition[]; total: number; limit: number; offset: number };
const root = "/users/me/keyword-conditions";

export const keywordConditionsApi = {
  save: (post_type: "LOST" | "FOUND", conditions: PostFilters) =>
    withChatToken(token => request<KeywordCondition>(root, { post_type, conditions: normalizePostFilters(conditions) }, token)),
  list: (offset = 0) =>
    withChatToken(token => request<KeywordConditionPage>(`${root}?offset=${offset}`, undefined, token)),
  setNotification: (id: string, notification_enabled: boolean) =>
    withChatToken(token => request<KeywordCondition>(`${root}/${id}`, { notification_enabled }, token, "PATCH")),
  remove: (id: string) => withChatToken(token => request<void>(`${root}/${id}`, undefined, token, "DELETE")),
};
