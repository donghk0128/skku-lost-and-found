// Execute the production native adapter with in-memory platform/transport doubles.
// No device, account, private key or network is involved.
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import vm from "node:vm";
import ts from "typescript";

export const ownerId = "56c55091-d4e1-4199-bba6-634551e552f3";
export const postId = "c3459c24-7401-4a2f-a2bf-012a3dc527f5";
export const notificationId = "6009a1ae-63c7-4102-85bd-d42b7ca2fd36";
export const installationId = "717ba5a4-889b-4b70-a105-aad6191a09fb";
export const preferenceKey = "lost-found-notifications";

export function deferred() {
  let resolve;
  const promise = new Promise(done => { resolve = done; });
  return { promise, resolve };
}

export const flush = () => new Promise(resolve => setImmediate(resolve));

export function runtime() {
  const store = new Map([["push-installation-id", installationId]]);
  const state = {
    store, session: { access_token: "access-a", refresh_token: "refresh-a" },
    permission: { granted: true, canAskAgain: true }, requests: [], displayed: [], opened: [],
    registrations: 0, unregistrations: 0, prompts: 0, dismissed: 0,
    onRequest: async () => {}, onRefresh: async () => ({ access_token: "refreshed-a" }),
    fid: "registeredFirebaseInstallationId",
  };
  const registrations = new Set();
  const messaging = { isDeviceRegisteredForRemoteMessages: true };
  class ApiError extends Error { constructor(status) { super("API failure"); this.status = status; } }
  const fcm = {
    getMessaging: () => messaging,
    setBackgroundMessageHandler: (_messaging, callback) => { state.background = callback; },
    onRegistered: (_messaging, callback) => { registrations.add(callback); return () => registrations.delete(callback); },
    register: async () => { state.registrations++; registrations.forEach(callback => callback(state.fid)); },
    unregister: async () => { state.unregistrations++; },
    registerDeviceForRemoteMessages: async () => {},
    onMessage: (_messaging, callback) => { state.message = callback; return () => { state.message = null; }; },
    onNotificationOpenedApp: (_messaging, callback) => { state.openedMessage = callback; return () => { state.openedMessage = null; }; },
    getInitialNotification: async () => null,
  };
  const notifications = {
    IosAuthorizationStatus: { PROVISIONAL: 3 }, AndroidImportance: { HIGH: 4 },
    getPermissionsAsync: async () => state.permission,
    requestPermissionsAsync: async () => { state.prompts++; return state.permission; },
    setNotificationChannelAsync: async () => {},
    dismissAllNotificationsAsync: async () => { state.dismissed++; },
    setNotificationHandler: value => { state.handler = value; },
    scheduleNotificationAsync: async value => { state.displayed.push(value); },
    addNotificationResponseReceivedListener: callback => { state.response = callback; return { remove() {} }; },
    getLastNotificationResponse: () => null,
    clearLastNotificationResponseAsync: async () => {},
  };
  const mocks = {
    "expo-constants": { __esModule: true, default: { executionEnvironment: "standalone" }, ExecutionEnvironment: { StoreClient: "storeClient" } },
    "expo-crypto": { randomUUID: () => installationId },
    "expo-secure-store": { getItemAsync: async key => store.get(key) ?? null, setItemAsync: async (key, value) => { store.set(key, value); } },
    "react-native": { Platform: { OS: "android" }, AppState: { addEventListener: (_event, callback) => { state.appState = callback; return { remove() {} }; } } },
    "@react-native-firebase/messaging": fcm,
    "expo-notifications": notifications,
    "@/lib/auth-api": {
      ApiError, authApi: { refresh: (...args) => state.onRefresh(...args) },
      request: async (path, body, accessToken, method) => {
        const value = { path, body, accessToken, method: method ?? (body ? "POST" : "GET") };
        state.requests.push(value);
        return state.onRequest(value);
      },
    },
    "@/lib/session-storage": { readSession: async () => state.session, writeSession: async value => { state.session = value; } },
    "@/i18n": { t: key => key },
  };
  const cache = new Map();
  function load(name) {
    if (name in mocks) return mocks[name];
    if (cache.has(name)) return cache.get(name).exports;
    const filename = name.startsWith("@/") ? name.slice(2) + ".ts" : name;
    const path = fileURLToPath(new URL("../../src/" + filename, import.meta.url));
    const code = ts.transpileModule(readFileSync(path, "utf8"), {
      compilerOptions: { module: ts.ModuleKind.CommonJS, target: ts.ScriptTarget.ES2022, esModuleInterop: true },
    }).outputText;
    const module = { exports: {} };
    cache.set(name, module);
    vm.runInNewContext(code, { require: load, module, exports: module.exports, setTimeout, clearTimeout }, { filename: path });
    return module.exports;
  }
  return { state, ApiError, client: load("lib/push-client.native.ts"), preference: load("@/lib/notification-preference") };
}
