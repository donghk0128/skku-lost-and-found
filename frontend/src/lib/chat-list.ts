import type { ChatRoom } from "@/lib/chat-api";

export function filterChatRooms(rooms: ChatRoom[], query: string): ChatRoom[] {
  const terms = query.normalize("NFKC").trim().toLocaleLowerCase().split(/\s+/).filter(Boolean);
  if (!terms.length) return rooms;
  return rooms.filter(room => {
    const text = [room.other_nickname, room.post_title, room.last_message?.content ?? ""]
      .join(" ").normalize("NFKC").toLocaleLowerCase();
    return terms.every(term => text.includes(term));
  });
}

export function relativeChatTime(value: string | undefined, now: number, locale: string): string {
  if (!value) return "";
  const timestamp = new Date(value).getTime();
  if (!Number.isFinite(timestamp)) return "";
  const minutes = Math.max(0, Math.floor((now - timestamp) / 60000));
  // Some native JS runtimes do not provide Intl.RelativeTimeFormat.
  const english = locale === "en";
  if (minutes < 1) return english ? "Just now" : "방금 전";
  const [count, koUnit, enUnit] = minutes < 60
    ? [minutes, "분", "minute"] as const
    : minutes < 1440
      ? [Math.floor(minutes / 60), "시간", "hour"] as const
      : [Math.floor(minutes / 1440), "일", "day"] as const;
  return english
    ? `${count} ${enUnit}${count === 1 ? "" : "s"} ago`
    : `${count}${koUnit} 전`;
}
