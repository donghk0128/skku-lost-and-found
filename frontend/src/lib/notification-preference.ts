import * as SecureStore from "expo-secure-store";
import { Platform } from "react-native";

// Preserve the preference key introduced by the account screen.
export const notificationPreferenceKey = "lost-found-notifications";
const listeners = new Set<() => void>();

export async function notificationsEnabledOnDevice(): Promise<boolean> {
  return Platform.OS !== "web" && await SecureStore.getItemAsync(notificationPreferenceKey) === "on";
}

export async function writeNotificationPreference(enabled: boolean): Promise<void> {
  if (Platform.OS === "web") return;
  await SecureStore.setItemAsync(notificationPreferenceKey, enabled ? "on" : "off");
  listeners.forEach(listener => listener());
}

export function onNotificationPreferenceChange(listener: () => void): () => void {
  listeners.add(listener);
  return () => { listeners.delete(listener); };
}
