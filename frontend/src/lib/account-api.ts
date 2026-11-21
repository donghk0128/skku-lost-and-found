import { request, type User } from "@/lib/auth-api";
import { withChatToken } from "@/lib/chat-api";
import type { Post } from "@/lib/posts-api";

export type AccountPostPage = { items: Post[]; total: number; limit: number; offset: number };
const root = "/users/me";

export const accountApi = {
  startWithdrawal: (current_password: string) =>
    withChatToken(token => request<{ withdrawal_token: string; expires_at: string }>(`${root}/withdrawal/password`, { current_password }, token)),
  sendWithdrawalCode: (withdrawal_token: string) =>
    withChatToken(token => request<{ expires_at: string; resend_available_at: string }>(`${root}/withdrawal/send-code`, { withdrawal_token }, token)),
  verifyWithdrawalEmail: (withdrawal_token: string, code: string) =>
    withChatToken(token => request<{ expires_at: string }>(`${root}/withdrawal/verify-email`, { withdrawal_token, code }, token)),
  withdraw: (withdrawal_token: string) =>
    withChatToken(token => request<void>(root, { withdrawal_token, confirmed: true }, token, "DELETE")),
  updateProfile: (nickname: string) =>
    withChatToken(token => request<User>(root, { nickname }, token, "PATCH")),
  changePassword: (current_password: string, password: string, password_confirmation: string) =>
    withChatToken(token => request<{ message: string }>(`${root}/password`, { current_password, password, password_confirmation }, token)),
  myPosts: (type: "LOST" | "FOUND", offset = 0) =>
    withChatToken(token => request<AccountPostPage>(`${root}/posts?post_type=${type}&offset=${offset}`, undefined, token)),
  favorites: (offset = 0) =>
    withChatToken(token => request<AccountPostPage>(`${root}/favorites?offset=${offset}`, undefined, token)),
  favoriteState: (id: string) =>
    withChatToken(token => request<{ saved: boolean }>(`${root}/favorites/${id}`, undefined, token)),
  setFavorite: (id: string, saved: boolean) =>
    withChatToken(token => request<void>(`${root}/favorites/${id}`, saved ? {} : undefined, token, saved ? undefined : "DELETE")),
};
