import type { ReactNode } from "react";
import { StyleSheet, Text, View } from "react-native";
import ChatImageGallery from "@/components/ChatImageGallery";
import { Colors, Fonts } from "@/constants/theme";
import type { ChatMessage } from "@/lib/chat-api";

export default function ChatMessageBubble({
  message,
  own,
  locale,
  showTime = true,
  showAvatar = true,
  avatar,
  compact = false,
  children,
}: {
  message: Pick<ChatMessage, "content"> &
    Partial<Pick<ChatMessage, "created_at" | "images">>;
  own: boolean;
  locale: "ko" | "en";
  showTime?: boolean;
  showAvatar?: boolean;
  avatar?: ReactNode;
  compact?: boolean;
  children?: ReactNode;
}) {
  const time =
    showTime && message.created_at
      ? new Date(message.created_at).toLocaleTimeString(
          locale === "en" ? "en-US" : "ko-KR",
          { hour: "2-digit", minute: "2-digit", hour12: false },
        )
      : null;

  return (
    <View style={[styles.row, own && styles.ownRow]}>
      {!own && showAvatar ? (avatar ? <View style={styles.customAvatar}>{avatar}</View> : <View style={styles.avatar} />) : null}
      {own && time ? <Text style={styles.time}>{time}</Text> : null}
      <View
        style={[
          styles.bubble,
          compact && styles.compactBubble,
          own && styles.ownBubble,
          compact && own && styles.compactOwnBubble,
        ]}
      >
        {children}
        {message.images?.length ? (
          <ChatImageGallery images={message.images} />
        ) : null}
        {message.content ? (
          <Text
            selectable
            style={[
              styles.messageText,
              compact && styles.compactText,
              own && styles.ownText,
            ]}
          >
            {message.content}
          </Text>
        ) : null}
      </View>
      {!own && time ? <Text style={styles.time}>{time}</Text> : null}
    </View>
  );
}

const styles = StyleSheet.create({
  row: {
    flexDirection: "row",
    alignItems: "flex-end",
    gap: 8,
    paddingRight: 20,
  },
  ownRow: { justifyContent: "flex-end", paddingRight: 0, paddingLeft: 20 },
  customAvatar: { width: 28, height: 28, alignSelf: "flex-start", marginTop: 2 },
  avatar: {
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: "#D9D9D9",
    alignSelf: "flex-start",
  },
  bubble: {
    flexShrink: 1,
    paddingHorizontal: 18,
    paddingVertical: 15,
    gap: 8,
    borderRadius: 24,
    borderTopLeftRadius: 4,
    backgroundColor: "#F0F1F2",
  },
  ownBubble: {
    borderTopLeftRadius: 24,
    borderBottomRightRadius: 4,
    backgroundColor: Colors.primary,
  },
  messageText: {
    fontFamily: Fonts.pretendardRegular,
    fontSize: 16,
    lineHeight: 24,
    color: "#292D2E",
  },
  compactBubble: {
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 20,
    borderTopLeftRadius: 4,
  },
  compactOwnBubble: { borderTopLeftRadius: 20, borderBottomRightRadius: 4 },
  compactText: { fontSize: 14, lineHeight: 21 },
  ownText: { color: "#FFFFFF" },
  time: {
    flexShrink: 0,
    fontFamily: Fonts.pretendardRegular,
    fontSize: 12,
    color: "#999D9B",
    paddingBottom: 2,
  },
});
