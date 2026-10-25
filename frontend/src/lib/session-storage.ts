import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";
import type { Session } from "./auth-api";

const key = "lost-found-session";

export async function readSession(): Promise<Session | null> {
  const value = Platform.OS === "web"
    ? (typeof window === "undefined" ? null : window.sessionStorage.getItem(key))
    : await SecureStore.getItemAsync(key);
  if (!value) return null;
  try {
    const session = JSON.parse(value);
    return session && typeof session.access_token === "string" && typeof session.refresh_token === "string"
      ? session : null;
  } catch {
    return null;
  }
}

export async function writeSession(session: Session | null): Promise<void> {
  if (Platform.OS === "web") {
    if (session) window.sessionStorage.setItem(key, JSON.stringify(session));
    else window.sessionStorage.removeItem(key);
  } else if (session) {
    await SecureStore.setItemAsync(key, JSON.stringify(session));
  } else {
    await SecureStore.deleteItemAsync(key);
  }
}
