/** Accept only our post notification payload, never an arbitrary URL. */
export type PostPushPayload = { post_id: string; user_id: string; notification_id: string };
export type ChatPushPayload = { room_id: string; user_id: string; notification_id: string; sequence: number };
const uuid = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/i;

export function parsePostPush(data: unknown): PostPushPayload | null {
  if (!data || typeof data !== "object") return null;
  const value = data as Record<string, unknown>;
  if (value.type !== "keyword_post") return null;
  for (const key of ["post_id", "user_id", "notification_id"]) {
    if (typeof value[key] !== "string" || !uuid.test(value[key])) return null;
  }
  return value as PostPushPayload;
}

export function parseChatPush(data: unknown): ChatPushPayload | null {
  if (!data || typeof data !== "object") return null;
  const value = data as Record<string, unknown>;
  if (value.type !== "chat_message") return null;
  for (const key of ["room_id", "user_id", "notification_id"]) {
    if (typeof value[key] !== "string" || !uuid.test(value[key])) return null;
  }
  if (typeof value.sequence !== "string" || !/^[1-9][0-9]*$/.test(value.sequence)) return null;
  const sequence = Number(value.sequence);
  if (!Number.isSafeInteger(sequence)) return null;
  return { room_id: value.room_id as string, user_id: value.user_id as string,
    notification_id: value.notification_id as string, sequence };
}
