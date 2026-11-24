import Constants, { ExecutionEnvironment } from "expo-constants";
import * as Crypto from "expo-crypto";
import * as SecureStore from "expo-secure-store";
import { AppState, Platform } from "react-native";
import type * as Messaging from "@react-native-firebase/messaging";
import type * as ExpoNotifications from "expo-notifications";
import { ApiError, authApi, request } from "@/lib/auth-api";
import { readSession, writeSession } from "@/lib/session-storage";
import { parsePostPush } from "@/lib/push-payload";
import { t } from "@/i18n";
import { notificationsEnabledOnDevice, writeNotificationPreference } from "@/lib/notification-preference";

export type PushPermission = "granted" | "denied" | "unavailable";
export function initializePushBackground(): void {
  const native = nativeModules();
  // Visible background/terminated notifications are presented by the OS.
  native?.fcm.setBackgroundMessageHandler(native.fcm.getMessaging(), async () => {});
}
const installationKey = "push-installation-id";
let modules: { fcm: typeof Messaging; notifications: typeof ExpoNotifications } | undefined;
let registration: Promise<void> = Promise.resolve();
let cachedFid: string | undefined;
let unsubscribeFid: (() => void) | undefined;
let registeredFid: ((fid: string) => void) | undefined;

function nativeModules() {
  if (Constants.executionEnvironment === ExecutionEnvironment.StoreClient) return null;
  if (!modules) {
    // Lazy imports preserve Expo Go and web flows when native configuration is absent.
    try {
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      const fcm = require("@react-native-firebase/messaging") as typeof Messaging;
      // eslint-disable-next-line @typescript-eslint/no-require-imports
      const notifications = require("expo-notifications") as typeof ExpoNotifications;
      fcm.getMessaging();
      modules = { fcm, notifications };
    } catch { return null; }
  }
  return modules;
}

async function installationId() {
  let id = await SecureStore.getItemAsync(installationKey);
  if (!id) { id = Crypto.randomUUID(); await SecureStore.setItemAsync(installationKey, id); }
  return id;
}

async function permitted() {
  const native = nativeModules();
  if (!native) return false;
  const permission = await native.notifications.getPermissionsAsync();
  return permission.granted || permission.ios?.status === native.notifications.IosAuthorizationStatus.PROVISIONAL;
}

async function ensureChannel() {
  const native = nativeModules();
  if (native && Platform.OS === "android") await native.notifications.setNotificationChannelAsync("keyword-posts", {
    name: t("push.channel"), importance: native.notifications.AndroidImportance.HIGH,
  });
}

async function uploadFid(fid: string) {
  const original = await readSession();
  if (!original || !await notificationsEnabledOnDevice() || !await permitted()) return;
  const id = await installationId();
  async function send(accessToken: string) {
    const current = await readSession();
    if (current?.refresh_token !== original!.refresh_token || !await notificationsEnabledOnDevice()) return;
    await request("/users/me/push-devices", {
      installation_id: id, platform: Platform.OS, fid, refresh_token: original!.refresh_token,
    }, accessToken);
  }
  try { await send(original.access_token); }
  catch (error) {
    if (!(error instanceof ApiError) || error.status !== 401) throw error;
    const refreshed = await authApi.refresh(original.refresh_token);
    const current = await readSession();
    if (current?.refresh_token !== original.refresh_token) return;
    await writeSession({ ...original, access_token: refreshed.access_token });
    await send(refreshed.access_token);
  }
}

// Serialize registration and logout so an in-flight upload cannot undo detachment.
function serialize(action: () => Promise<void>) {
  const result = registration.catch(() => undefined).then(action);
  registration = result;
  return result;
}

export async function syncPush(): Promise<void> {
  return serialize(async () => {
    const native = nativeModules();
    if (!native) return;
    await ensureChannel();
    if (!await notificationsEnabledOnDevice() || !await permitted()) {
      await detachRegistration();
      return;
    }
    const messaging = native.fcm.getMessaging();
    if (Platform.OS === "ios" && !messaging.isDeviceRegisteredForRemoteMessages) {
      await native.fcm.registerDeviceForRemoteMessages(messaging);
    }
    if (!unsubscribeFid) {
      unsubscribeFid = native.fcm.onRegistered(messaging, fid => {
        cachedFid = fid;
        registeredFid?.(fid);
        void serialize(() => uploadFid(fid)).catch(() => undefined);
      });
    }
    await native.fcm.register(messaging);
    const fid = cachedFid ?? await new Promise<string>((resolve, reject) => {
      const timer = setTimeout(() => { registeredFid = undefined; reject(new Error(t("push.registrationFailed"))); }, 15000);
      registeredFid = value => { clearTimeout(timer); registeredFid = undefined; resolve(value); };
    });
    await uploadFid(fid);
  });
}

export async function enablePush(): Promise<PushPermission> {
  const native = nativeModules();
  if (!native) return "unavailable";
  await ensureChannel();
  await native.notifications.requestPermissionsAsync();
  if (!await permitted()) return "denied";
  await writeNotificationPreference(true);
  await syncPush();
  return "granted";
}

async function detachRegistration(): Promise<void> {
    unsubscribeFid?.(); unsubscribeFid = undefined; cachedFid = undefined;
    const native = nativeModules();
    if (!native) return;
    const session = await readSession();
    const id = await SecureStore.getItemAsync(installationKey);
    try {
      if (session && id) {
        try { await request(`/users/me/push-devices/${id}`, undefined, session.access_token, "DELETE"); }
        catch (error) {
          if (!(error instanceof ApiError) || error.status !== 401) throw error;
          const refreshed = await authApi.refresh(session.refresh_token);
          const current = await readSession();
          if (current?.refresh_token === session.refresh_token) {
            await writeSession({ ...session, access_token: refreshed.access_token });
            await request(`/users/me/push-devices/${id}`, undefined, refreshed.access_token, "DELETE");
          }
        }
      }
    } finally {
      try { await native.fcm.unregister(native.fcm.getMessaging()); }
      finally { await native.notifications.dismissAllNotificationsAsync(); }
    }
}

export async function clearPush(): Promise<void> {
  return serialize(detachRegistration);
}

export function observePush(userId: string, openPost: (id: string) => void): () => void {
  const native = nativeModules();
  if (!native) return () => {};
  const { fcm, notifications } = native;
  let active = true;
  const seen = new Set<string>();
  const presented = new Set<string>();
  function open(data: unknown) {
    const payload = parsePostPush(data);
    if (!active || !payload || payload.user_id !== userId || seen.has(payload.notification_id)) return;
    seen.add(payload.notification_id);
    openPost(payload.post_id);
  }
  notifications.setNotificationHandler({ handleNotification: async notification => {
    const payload = parsePostPush(notification.request.content.data);
    // RN Firebase handles remote receipt; Expo presents only our local banner.
    // Suppress remote auto-presentation so the same message cannot show twice.
    const trigger = notification.request.trigger;
    const remote = trigger && "type" in trigger && trigger.type === "push";
    const show = active && payload?.user_id === userId && !remote && await notificationsEnabledOnDevice();
    return { shouldShowBanner: show, shouldShowList: show, shouldPlaySound: show, shouldSetBadge: false };
  } });
  const messaging = fcm.getMessaging();
  const stopForeground = fcm.onMessage(messaging, async message => {
    const payload = parsePostPush(message.data);
    if (!active || !payload || payload.user_id !== userId || presented.has(payload.notification_id)
      || !await notificationsEnabledOnDevice()) return;
    presented.add(payload.notification_id);
    if (presented.size > 500) presented.delete(presented.values().next().value!);
    await notifications.scheduleNotificationAsync({
      identifier: payload.notification_id,
      content: { title: message.notification?.title, body: message.notification?.body,
        data: message.data, sound: "default" },
      trigger: Platform.OS === "android" ? { channelId: "keyword-posts" } : null,
    });
  });
  const stopOpened = fcm.onNotificationOpenedApp(messaging, message => open(message.data));
  const response = notifications.addNotificationResponseReceivedListener(event => open(event.notification.request.content.data));
  const last = notifications.getLastNotificationResponse();
  if (last) open(last.notification.request.content.data);
  void notifications.clearLastNotificationResponseAsync();
  void fcm.getInitialNotification(messaging).then(message => { if (message) open(message.data); }).catch(() => undefined);
  const appState = AppState.addEventListener("change", state => {
    if (state === "active") void syncPush().catch(() => undefined);
  });
  void syncPush().catch(() => undefined);
  return () => { active = false; stopForeground(); stopOpened(); response.remove(); appState.remove(); };
}
