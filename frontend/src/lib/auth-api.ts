import { Platform } from "react-native";

export type User = {
  id: string;
  email: string;
  nickname: string;
  email_verified_at: string;
  created_at: string;
};

export type Session = { access_token: string; refresh_token: string };
export type AuthResponse = Session & { user: User };

export const baseUrl = (
  process.env.EXPO_PUBLIC_API_URL ??
  (Platform.OS === "android"
    ? "http://10.0.2.2:8000/api/v1"
    : "http://localhost:8000/api/v1")
).replace(/\/$/, "");

export class ApiError extends Error {
  constructor(
    public status: number,
    message: string,
  ) {
    super(message);
  }
}

export async function request<T>(
  path: string,
  body?: object,
  token?: string,
  method?: "PATCH" | "DELETE",
): Promise<T> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(`${baseUrl}${path}`, {
      method: method ?? (body ? "POST" : "GET"),
      headers: {
        ...(body ? { "Content-Type": "application/json" } : {}),
        ...(token ? { Authorization: `Bearer ${token}` } : {}),
      },
      body: body ? JSON.stringify(body) : undefined,
      signal: controller.signal,
    });
    if (response.status === 204) return undefined as T;
    const data = await response.json();
    if (!response.ok) {
      throw new ApiError(
        response.status,
        data.error?.message ?? "요청을 처리하지 못했습니다.",
      );
    }
    return data as T;
  } catch (error) {
    if (error instanceof ApiError) throw error;
    throw new Error(
      "서버에 연결하지 못했습니다. 서버 실행 상태와 API 주소를 확인해주세요.",
    );
  } finally {
    clearTimeout(timeout);
  }
}

export const authApi = {
  signOut: (refresh_token: string) =>
    request<{ message: string }>("/auth/logout", { refresh_token }),
  sendCode: (email: string) =>
    request<{ message: string }>("/auth/email/send-code", { email }),
  verifyCode: (email: string, code: string) =>
    request<{ message: string }>("/auth/email/verify", { email, code }),
  signIn: (email: string, password: string) =>
    request<AuthResponse>("/auth/login", { email, password }),
  signUp: (email: string, nickname: string, password: string) =>
    request<AuthResponse>("/auth/signup", { email, nickname, password }),
  me: (token: string) => request<User>("/users/me", undefined, token),
  refresh: (refresh_token: string) =>
    request<{ access_token: string }>("/auth/refresh", { refresh_token }),
};
