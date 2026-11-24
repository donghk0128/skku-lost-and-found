/** Accept only our post notification payload, never an arbitrary URL. */
export type PostPushPayload = { post_id: string; user_id: string; notification_id: string };
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
