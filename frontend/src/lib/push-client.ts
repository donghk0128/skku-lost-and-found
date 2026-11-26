// Web does not register for native remote notifications.
export type PushPermission = "granted" | "denied" | "unavailable";
export async function enablePush(): Promise<PushPermission> { return "unavailable"; }
export async function syncPush(): Promise<void> {}
export async function clearPush(): Promise<void> {}
export function initializePushBackground(): void {}
export function observePush(_userId: string, _openPost: (id: string) => void, _openChat: (id: string) => void): () => void { return () => {}; }
