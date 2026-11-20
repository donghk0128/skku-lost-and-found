import { StyleSheet, Text, View } from "react-native";
import ChatImageGallery from "@/components/ChatImageGallery";
import { Colors, Fonts } from "@/constants/theme";
import type { ChatMessage } from "@/lib/chat-api";

export default function ChatMessageBubble({
  message,
  own,
  locale,
}: {
  message: ChatMessage;
  own: boolean;
  locale: "ko" | "en";
}) {
  const time = new Date(message.created_at).toLocaleTimeString(
    locale === "en" ? "en-US" : "ko-KR",
    { hour: "2-digit", minute: "2-digit", hour12: false },
  );

  return (
    <View style={[styles.row, own && styles.ownRow]}>
      {!own ? <View style={styles.avatar} /> : null}
      {own ? <Text style={styles.time}>{time}</Text> : null}
      <View style={[styles.bubble, own && styles.ownBubble]}>
        {message.images?.length ? (
          <ChatImageGallery images={message.images} />
        ) : null}
        {message.content ? (
          <Text selectable style={[styles.messageText, own && styles.ownText]}>
            {message.content}
          </Text>
        ) : null}
      </View>
      {!own ? <Text style={styles.time}>{time}</Text> : null}
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
  ownText: { color: "#FFFFFF" },
  time: {
    flexShrink: 0,
    fontFamily: Fonts.pretendardRegular,
    fontSize: 12,
    color: "#999D9B",
    paddingBottom: 2,
  },
});
