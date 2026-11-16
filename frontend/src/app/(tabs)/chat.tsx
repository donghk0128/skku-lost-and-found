import { useCallback, useState } from "react";
import { useFocusEffect, useRouter } from "expo-router";
import { ActivityIndicator, AppState, FlatList, Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Colors, Fonts, BottomTabInset } from "@/constants/theme";
import { chatApi, type ChatRoom } from "@/lib/chat-api";
import { useLocale } from "@/i18n/LocaleProvider";

export default function ChatList() {
  const router = useRouter();
  const { t } = useLocale();
  const [rooms, setRooms] = useState<ChatRoom[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [total, setTotal] = useState(0);
  const [hidden, setHidden] = useState(false);
  const [reload, setReload] = useState({ showLoading: true });
  const [pageLimit, setPageLimit] = useState(30);
  useFocusEffect(useCallback(() => {
    let active = true;
    let running = false;
    const load = async () => {
      if (running || AppState.currentState !== "active") return;
      running = true;
      try {
        const items: ChatRoom[] = [];
        let count = 0;
        do {
          const data = await chatApi.rooms(items.length, hidden);
          items.push(...data.items); count = data.total;
          if (!data.items.length) break;
        } while (items.length < count && items.length < pageLimit);
        if (active) { setRooms(items); setTotal(count); setError(""); }
      } catch (e) { if (active) setError(e instanceof Error ? e.message : t("common.requestFailed")); }
      finally { running = false; if (active) setLoading(false); }
    };
    setLoading(reload.showLoading);
    void load();
    const timer = setInterval(() => { void load(); }, 5000);
    return () => { active = false; clearInterval(timer); };
  }, [hidden, reload, pageLimit, t]));
  return <SafeAreaView style={styles.root}>
    <View style={styles.header}><Text style={styles.title}>{t("tabs.chat")}</Text>
      <Pressable accessibilityRole="button" onPress={() => setHidden(value => !value)}><Text style={styles.link}>{t(hidden ? "chat.hideHidden" : "chat.showHidden")}</Text></Pressable>
    </View>
    {error ? <Pressable onPress={() => setReload({ showLoading: true })}><Text accessibilityRole="alert" style={styles.error}>{error} · {t("common.retry")}</Text></Pressable> : null}
    <FlatList data={rooms} keyExtractor={item => item.id} contentContainerStyle={styles.list}
      refreshing={loading} onRefresh={() => setReload({ showLoading: true })}
      ListEmptyComponent={loading ? <ActivityIndicator color={Colors.primary} /> : <Text style={styles.empty}>{t("chat.empty")}</Text>}
      ListFooterComponent={rooms.length < total ? <Pressable disabled={loading} onPress={() => setPageLimit(value => value + 30)}><Text style={styles.empty}>{t("chat.more")}</Text></Pressable> : null}
      renderItem={({ item }) => <Pressable accessibilityRole="button" style={styles.room}
        onPress={() => router.push({ pathname: "/chat/[id]", params: { id: item.id } })}>
        <View style={styles.avatar}><Text style={styles.avatarText}>{item.other_nickname.slice(0, 1)}</Text></View>
        <View style={styles.body}>
          <Text numberOfLines={1} style={styles.name}>{item.post_title} {item.status === "CLOSED" ? `· ${t("chat.closed")}` : ""}{item.is_hidden ? ` · ${t("chat.hidden")}` : ""}</Text>
          <Text numberOfLines={1} style={styles.post}>{item.other_nickname}</Text>
          <Text numberOfLines={1} style={styles.preview}>{item.last_message?.message_type === "IMAGE" ? t("chat.photo") : item.last_message?.content ?? t("chat.start")}</Text>
        </View>
        {item.unread_count ? <View style={styles.badge}><Text style={styles.badgeText}>{item.unread_count > 99 ? "99+" : item.unread_count}</Text></View> : null}
      </Pressable>} />
  </SafeAreaView>;
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: Colors.background },
  header: { flexDirection: "row", alignItems: "center", justifyContent: "space-between", padding: 24 },
  title: { fontFamily: Fonts.pretendardBold, fontSize: 28, color: "#17392E" },
  link: { color: Colors.primary, fontSize: 13, paddingVertical: 12 },
  list: { paddingHorizontal: 24, paddingBottom: BottomTabInset + 32, maxWidth: 720, width: "100%", alignSelf: "center" },
  room: { flexDirection: "row", gap: 14, paddingVertical: 20, alignItems: "center", borderBottomWidth: 1, borderBottomColor: "#E7ECE9" },
  avatar: { width: 48, height: 48, borderRadius: 24, alignItems: "center", justifyContent: "center", backgroundColor: Colors.softgreen },
  avatarText: { fontFamily: Fonts.pretendardBold, color: Colors.primary, fontSize: 18 },
  body: { flex: 1, gap: 5 }, name: { fontFamily: Fonts.pretendardSemiBold, color: "#17392E", fontSize: 16 },
  post: { color: Colors.primary, fontSize: 12 }, preview: { color: "#6D7973", fontSize: 14 },
  badge: { borderRadius: 16, backgroundColor: Colors.primary, paddingHorizontal: 8, paddingVertical: 4 },
  badgeText: { color: "white", fontSize: 12 }, empty: { color: "#6D7973", textAlign: "center", padding: 32 },
  error: { color: "#B54747", paddingHorizontal: 24, paddingBottom: 16 },
});
