import { tabHeaderStyles } from "@/components/tab-header-styles";
import { useCallback, useRef, useState } from "react";
import { useFocusEffect, useRouter } from "expo-router";
import {
  ActivityIndicator,
  AppState,
  FlatList,
  Modal,
  Pressable,
  StyleSheet,
  Text,
  TextInput,
  useWindowDimensions,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import Svg, { Circle, Path } from "react-native-svg";
import SettingIcon from "@/assets/icons/setting.svg";
import { Colors, Fonts, BottomTabInset } from "@/constants/theme";
import { chatApi, type ChatRoom } from "@/lib/chat-api";
import { filterChatRooms, relativeChatTime } from "@/lib/chat-list";
import { useLocale } from "@/i18n/LocaleProvider";

export default function ChatList() {
  const router = useRouter();
  const { t, locale } = useLocale();
  const [rooms, setRooms] = useState<ChatRoom[]>([]);
  const [loading, setLoading] = useState(true);
  const [refreshing, setRefreshing] = useState(false);
  const searchInput = useRef<TextInput>(null);
  const [error, setError] = useState("");
  const [total, setTotal] = useState(0);
  const [hidden, setHidden] = useState(false);
  const [query, setQuery] = useState("");
  const [oldestFirst, setOldestFirst] = useState(false);
  const [sortMenuOpen, setSortMenuOpen] = useState(false);
  const sortTrigger = useRef<View>(null);
  const { width: windowWidth, height: windowHeight } = useWindowDimensions();
  const [sortAnchor, setSortAnchor] = useState({ left: 16, top: 64 });
  const sortMenuWidth = Math.min(132, windowWidth - 32);
  const showSortMenu = () => {
    searchInput.current?.blur();
    sortTrigger.current?.measureInWindow((x, y, _width, height) => {
      setSortAnchor({ left: x, top: y + height + 8 });
      setSortMenuOpen(true);
    });
  };
  const selectSort = (oldest: boolean) => {
    setOldestFirst(oldest);
    setSortMenuOpen(false);
  };
  const [now, setNow] = useState(() => Date.now());
  const [reload, setReload] = useState(0);
  const [pageLimit, setPageLimit] = useState(30);
  const searching = query.trim().length > 0;
  // Search and oldest-first sorting must include rooms beyond the first page.
  const loadAll = searching || oldestFirst;
  // Clear native pull-to-refresh and input focus when leaving the list.
  // This effect stays stable while a manual refresh restarts the data effect.
  useFocusEffect(
    useCallback(
      () => () => {
        setRefreshing(false);
        setSortMenuOpen(false);
        searchInput.current?.blur();
      },
      [],
    ),
  );
  useFocusEffect(
    useCallback(() => {
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
            if (!active) return;
            items.push(...data.items);
            count = data.total;
            if (!data.items.length) break;
          } while (
            items.length < count &&
            (loadAll || items.length < pageLimit)
          );
          if (active) {
            setRooms([
              ...new Map(items.map((item) => [item.id, item])).values(),
            ]);
            setTotal(count);
            setNow(Date.now());
            setError("");
          }
        } catch (e) {
          if (active)
            setError(
              e instanceof Error ? e.message : t("common.requestFailed"),
            );
        } finally {
          running = false;
          if (active) {
            setLoading(false);
            setRefreshing(false);
          }
        }
      };
      setLoading(true);
      void load();
      const timer = setInterval(() => {
        void load();
      }, 5000);
      return () => {
        active = false;
        clearInterval(timer);
      };
    }, [hidden, reload, pageLimit, loadAll, t]),
  );

  const filtered = filterChatRooms(rooms, query);
  const visibleRooms = oldestFirst ? [...filtered].reverse() : filtered;
  return (
    <SafeAreaView style={styles.root} edges={["top", "left", "right"]}>
      <View style={[tabHeaderStyles.container, styles.content]}>
        <View style={[tabHeaderStyles.row, styles.header]}>
          <Text style={styles.title}>{t("tabs.chat")}</Text>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={t("home.settings")}
            onPress={() => router.push("/settings")}
            style={styles.iconButton}
          >
            <SettingIcon width={26} height={26} />
          </Pressable>
        </View>
        <View style={styles.search}>
          <Svg
            width={22}
            height={22}
            viewBox="0 0 24 24"
            fill="none"
            stroke="#292D32"
            strokeWidth={1.7}
            strokeLinecap="round"
          >
            <Circle cx={10.5} cy={10.5} r={7.5} />
            <Path d="m16 16 5 5" />
          </Svg>
          <TextInput
            ref={searchInput}
            accessibilityLabel={t("chat.searchAccessibility")}
            placeholder={t("home.searchPlaceholder")}
            placeholderTextColor="#A0A0A0"
            value={query}
            onChangeText={setQuery}
            autoCapitalize="none"
            autoCorrect={false}
            returnKeyType="search"
            style={styles.searchInput}
          />
          {query ? (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={t("chat.clearSearch")}
              onPress={() => setQuery("")}
              hitSlop={8}
              style={styles.clearButton}
            >
              <Svg
                width={18}
                height={18}
                viewBox="0 0 24 24"
                fill="none"
                stroke="#888"
                strokeWidth={1.7}
                strokeLinecap="round"
              >
                <Path d="m6 6 12 12M18 6 6 18" />
              </Svg>
            </Pressable>
          ) : null}
        </View>
        <View style={styles.toolbar}>
          <Text style={styles.listTitle}>{t("chat.listTitle")}</Text>
          <Pressable
            ref={sortTrigger}
            accessibilityRole="button"
            accessibilityLabel={t(
              oldestFirst ? "chat.sortOldest" : "chat.sortNewest",
            )}
            accessibilityState={{ expanded: sortMenuOpen }}
            onPress={showSortMenu}
            hitSlop={{ top: 6, bottom: 6 }}
            style={styles.sortButton}
          >
            <Svg
              width={17}
              height={17}
              viewBox="0 0 24 24"
              fill="none"
              stroke="#292D32"
              strokeWidth={1.5}
              strokeLinecap="round"
              strokeLinejoin="round"
            >
              <Path d="M7 3v18m-4-4 4 4 4-4M17 21V3m-4 4 4-4 4 4" />
            </Svg>
            <Text style={styles.sortText}>
              {t(oldestFirst ? "chat.oldest" : "chat.newest")}
            </Text>
          </Pressable>
          <Pressable
            accessibilityRole="button"
            accessibilityState={{ selected: hidden }}
            onPress={() => setHidden((value) => !value)}
            style={styles.hiddenButton}
          >
            <Text style={[styles.hiddenText, hidden && styles.hiddenSelected]}>
              {t(hidden ? "chat.hideHidden" : "chat.showHidden")}
            </Text>
          </Pressable>
        </View>
        {error ? (
          <Pressable
            accessibilityRole="button"
            onPress={() => setReload((value) => value + 1)}
          >
            <Text accessibilityRole="alert" style={styles.error}>
              {error} · {t("common.retry")}
            </Text>
          </Pressable>
        ) : null}
        <FlatList
          style={styles.list}
          data={visibleRooms}
          keyExtractor={(item) => item.id}
          contentContainerStyle={styles.listContent}
          keyboardShouldPersistTaps="handled"
          keyboardDismissMode="on-drag"
          contentInsetAdjustmentBehavior="never"
          automaticallyAdjustContentInsets={false}
          refreshing={refreshing}
          onRefresh={() => {
            setRefreshing(true);
            setReload((value) => value + 1);
          }}
          ListEmptyComponent={
            loading ? (
              <ActivityIndicator
                color={Colors.primary}
                style={styles.emptyLoader}
              />
            ) : (
              <Text style={styles.empty}>
                {t(searching ? "chat.searchEmpty" : "chat.empty")}
              </Text>
            )
          }
          ListFooterComponent={
            rooms.length < total ? (
              loading ? (
                <ActivityIndicator
                  color={Colors.primary}
                  style={styles.emptyLoader}
                />
              ) : (
                <Pressable
                  accessibilityRole="button"
                  onPress={() => setPageLimit((value) => value + 30)}
                >
                  <Text style={styles.empty}>{t("chat.more")}</Text>
                </Pressable>
              )
            ) : null
          }
          renderItem={({ item }) => (
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={[
                item.other_nickname,
                item.post_title,
                item.last_message?.content,
                item.unread_count
                  ? t("chat.unreadCount", { count: item.unread_count })
                  : null,
              ]
                .filter(Boolean)
                .join(", ")}
              style={({ pressed }) => [
                styles.room,
                pressed && styles.roomPressed,
              ]}
              onPress={() =>
                router.push({ pathname: "/chat/[id]", params: { id: item.id } })
              }
            >
              <View style={styles.nameRow}>
                <Text numberOfLines={1} style={styles.name}>
                  {item.other_withdrawn ? t("chat.withdrawnUser") : item.other_nickname}
                </Text>
                <Text style={styles.time}>
                  {relativeChatTime(item.last_message?.created_at, now, locale)}
                </Text>
                {item.status === "CLOSED" ? (
                  <Text style={styles.status}>{t("chat.closed")}</Text>
                ) : null}
                {item.is_hidden ? (
                  <Text style={styles.status}>{t("chat.hidden")}</Text>
                ) : null}
              </View>
              <View style={styles.previewRow}>
                <Text numberOfLines={1} style={styles.preview}>
                  {item.last_message?.content ||
                    (item.last_message?.message_type === "IMAGE"
                      ? t("chat.photo")
                      : t("chat.start"))}
                </Text>
                {item.unread_count > 0 ? (
                  <View style={styles.unreadDot} />
                ) : null}
              </View>
            </Pressable>
          )}
        />
      </View>
      <Modal
        visible={sortMenuOpen}
        transparent
        animationType="fade"
        statusBarTranslucent
        onRequestClose={() => setSortMenuOpen(false)}
      >
        <View style={styles.sortOverlay}>
          <Pressable
            style={StyleSheet.absoluteFill}
            accessibilityRole="button"
            accessibilityLabel={t("common.close")}
            onPress={() => setSortMenuOpen(false)}
          />
          <View
            accessibilityViewIsModal
            style={[
              styles.sortPopover,
              {
                width: sortMenuWidth,
                left: Math.max(
                  16,
                  Math.min(sortAnchor.left, windowWidth - sortMenuWidth - 16),
                ),
                top: Math.max(16, Math.min(sortAnchor.top, windowHeight - 136)),
              },
            ]}
          >
            {[false, true].map((oldest) => (
              <Pressable
                key={String(oldest)}
                accessibilityRole="radio"
                accessibilityState={{ checked: oldestFirst === oldest }}
                onPress={() => selectSort(oldest)}
                style={({ pressed }) => [
                  styles.sortOption,
                  pressed && styles.sortOptionPressed,
                ]}
              >
                <Text
                  style={[
                    styles.sortOptionText,
                    oldestFirst === oldest && styles.sortOptionSelected,
                  ]}
                >
                  {t(oldest ? "chat.oldest" : "chat.newest")}
                </Text>
              </Pressable>
            ))}
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  sortOverlay: { flex: 1 },
  sortPopover: {
    position: "absolute",
    borderRadius: 14,
    borderWidth: 1,
    borderColor: "#E1E4E8",
    padding: 4,
    backgroundColor: "white",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.08,
    shadowRadius: 10,
    elevation: 5,
  },
  sortOption: {
    minHeight: 48,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    gap: 12,
    paddingHorizontal: 14,
    paddingVertical: 10,
    borderRadius: 10,
  },
  sortOptionPressed: { backgroundColor: "#F3F5F4" },
  sortOptionText: {
    color: "#222",
    fontSize: 14,
    fontFamily: Fonts.pretendardRegular,
  },
  sortOptionSelected: {
    color: Colors.primary,
    fontFamily: Fonts.pretendardMedium,
  },
  root: { flex: 1, backgroundColor: Colors.background },
  content: { flex: 1 },
  header: { marginBottom: 28 },
  title: { fontFamily: Fonts.pretendardSemiBold, fontSize: 28, lineHeight: 32, color: "#111" },
  iconButton: {
    width: 44,
    height: 44,
    justifyContent: "center",
    alignItems: "center",
  },
  search: {
    minHeight: 42,
    flexDirection: "row",
    alignItems: "center",
    gap: 10,
    borderBottomWidth: 1,
    borderBottomColor: "#DADADA",
    paddingHorizontal: 2,
  },
  searchInput: {
    flex: 1,
    minWidth: 0,
    paddingVertical: 9,
    color: "#222",
    fontSize: 16,
    fontFamily: Fonts.pretendardRegular,
  },
  clearButton: {
    width: 28,
    height: 36,
    alignItems: "center",
    justifyContent: "center",
  },
  toolbar: {
    flexDirection: "row",
    flexWrap: "wrap",
    alignItems: "center",
    columnGap: 16,
    rowGap: 4,
    paddingTop: 20,
    paddingBottom: 10,
  },
  listTitle: {
    fontFamily: Fonts.pretendardSemiBold,
    fontSize: 18,
    color: "#111",
  },
  sortButton: {
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
    minHeight: 32,
    borderWidth: 1,
    borderColor: "#D7D7D7",
    borderRadius: 16,
    paddingHorizontal: 14,
  },
  sortText: {
    fontFamily: Fonts.pretendardRegular,
    fontSize: 14,
    color: "#222",
  },
  hiddenButton: { marginLeft: "auto", minHeight: 44, justifyContent: "center" },
  hiddenText: {
    color: "#929795",
    fontFamily: Fonts.pretendardRegular,
    fontSize: 11,
  },
  hiddenSelected: { color: Colors.primary },
  list: { flex: 1 },
  listContent: { flexGrow: 1, paddingBottom: BottomTabInset + 32 },
  room: {
    minHeight: 80,
    justifyContent: "center",
    gap: 8,
    paddingVertical: 16,
    borderRadius: 12,
  },
  roomPressed: { backgroundColor: "#F1F4F2" },
  nameRow: { flexDirection: "row", alignItems: "center", gap: 12 },
  name: {
    flexShrink: 1,
    fontFamily: Fonts.pretendardMedium,
    color: "#111",
    fontSize: 18,
  },
  time: { color: "#999", fontFamily: Fonts.pretendardRegular, fontSize: 14 },
  status: { color: "#999", fontSize: 11, flexShrink: 1 },
  previewRow: { flexDirection: "row", alignItems: "center", gap: 14 },
  preview: {
    flexShrink: 1,
    color: "#999",
    fontFamily: Fonts.pretendardRegular,
    fontSize: 15,
    lineHeight: 21,
  },
  unreadDot: {
    width: 6,
    height: 6,
    borderRadius: 3,
    backgroundColor: "#FF424D",
  },
  empty: {
    color: "#888",
    textAlign: "center",
    paddingVertical: 32,
    fontFamily: Fonts.pretendardRegular,
    fontSize: 14,
  },
  emptyLoader: { marginVertical: 32 },
  error: { color: "#B54747", paddingBottom: 12, fontSize: 13 },
});
