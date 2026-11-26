import { tabHeaderStyles } from "@/components/tab-header-styles";
import { useCallback, useEffect, useState } from "react";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import {
  Keyboard,
  Pressable,
  ScrollView,
  StyleSheet,
  TextInput,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { ThemedText } from "@/components/themed-text";
import {
  BottomTabInset,
  Colors,
  Fonts,
  MaxContentWidth,
} from "@/constants/theme";
import PostBoard from "@/components/post-board";
import PostFilterDialog from "@/components/post-filter-dialog";
import { emptyPostFilters, hasPostFilters } from "@/lib/post-filters";
import CreatePostButton from "@/components/create-post-button";
import SettingIcon from "@/assets/icons/setting.svg";
import { useLocale } from "@/i18n/LocaleProvider";
import LanguageSelector from "@/components/language-selector";
import { postsApi, type Category, type Post } from "@/lib/posts-api";
import { readSession } from "@/lib/session-storage";
import { useAuth } from "@/providers/AuthProvider";
import { newVisitId, trackEvent } from "@/lib/event-logging";

type BoardTab = "lost" | "found";
type SortMode = "newest" | "candidates";

export default function HomeScreen() {
  useFocusEffect(useCallback(() => {
    trackEvent({ event_type: "screen_view", screen: "home", visit_id: newVisitId() });
  }, []));
  const { t } = useLocale();
  const { user } = useAuth();
  const router = useRouter();
  const params = useLocalSearchParams<{ board?: string; refresh?: string }>();
  const [selectedTab, setActiveTab] = useState<{
    tab: BoardTab;
    version?: string;
  }>({ tab: "lost" });
  const activeTab =
    params.refresh && selectedTab.version !== params.refresh
      ? params.board === "FOUND"
        ? "found"
        : "lost"
      : selectedTab.tab;
  const [visitedBoards, setVisitedBoards] = useState<BoardTab[]>([]);
  const [filters, setFilters] = useState(emptyPostFilters);
  const [sortMode, setSortMode] = useState<SortMode>("newest");
  const [categories, setCategories] = useState<Category[]>([]);
  const [sources, setSources] = useState<Post[]>([]);
  const [selectedSourceIds, setSelectedSourceIds] = useState<
    Record<BoardTab, string | null>
  >({
    lost: null,
    found: null,
  });
  const [sourcesLoading, setSourcesLoading] = useState(false);
  const [sourceError, setSourceError] = useState("");
  const [sourceMenuOpen, setSourceMenuOpen] = useState(false);
  const [filterOpen, setFilterOpen] = useState(false);
  const sourceType = activeTab === "lost" ? "FOUND" : "LOST";
  const selectedSource = sources.find(
    (post) => post.id === selectedSourceIds[activeTab],
  );

  useEffect(() => {
    let active = true;
    postsApi
      .categories()
      .then((items) => {
        if (active) setCategories(items);
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, []);

  useFocusEffect(
    useCallback(() => {
      if (sortMode !== "candidates" || !user) return;
      let active = true;
      setSourcesLoading(true);
      setSourceError("");
      async function loadSources() {
        try {
          const session = await readSession();
          if (!session) throw new Error(t("common.loginRequired"));
          const result = await postsApi.mine(sourceType, session.access_token);
          if (!active) return;
          setSources(result.items);
          setSelectedSourceIds((current) => ({
            ...current,
            [activeTab]: result.items.some(
              (post) => post.id === current[activeTab],
            )
              ? current[activeTab]
              : null,
          }));
        } catch (error) {
          if (active)
            setSourceError(
              error instanceof Error
                ? error.message
                : t("common.postLoadFailed"),
            );
        } finally {
          if (active) setSourcesLoading(false);
        }
      }
      void loadSources();
      return () => {
        active = false;
      };
    }, [sortMode, sourceType, activeTab, user, t]),
  );

  const changeTab = (tab: BoardTab) => {
    Keyboard.dismiss();
    setSourceMenuOpen(false);
    setFilterOpen(false);
    setVisitedBoards((current) => Array.from(new Set([...current, activeTab, tab])));
    setActiveTab({ tab, version: params.refresh });
  };

  return (
    <View style={styles.container}>
      <SafeAreaView style={styles.safeArea} edges={["top", "left", "right"]}>
        <View style={[tabHeaderStyles.container, styles.content]}>
          {/* Header */}
          <View style={[tabHeaderStyles.row, styles.header]}>
            <ThemedText type="title" style={styles.logo}>
              SKKU Finder
            </ThemedText>

            <View style={styles.headerActions}>
              <LanguageSelector />
              <Pressable
                onPress={() => router.push("/settings")}
                accessibilityRole="button"
                accessibilityLabel={t("home.settings")}
                hitSlop={8}
                style={({ pressed }) => [
                  styles.settingsButton,
                  pressed && styles.pressed,
                ]}
              >
                <SettingIcon />
              </Pressable>
            </View>
          </View>

          {/* Board tabs */}
          <View style={styles.tabs}>
            <Pressable
              onPress={() => changeTab("lost")}
              accessibilityRole="tab"
              accessibilityState={{
                selected: activeTab === "lost",
              }}
              style={[styles.tab, activeTab === "lost" && styles.activeTab]}
            >
              <ThemedText
                style={[
                  styles.tabText,
                  activeTab === "lost" && styles.activeTabText,
                ]}
              >
                {t("home.lostTab")}
              </ThemedText>
            </Pressable>

            <Pressable
              onPress={() => changeTab("found")}
              accessibilityRole="tab"
              accessibilityState={{
                selected: activeTab === "found",
              }}
              style={[styles.tab, activeTab === "found" && styles.activeTab]}
            >
              <ThemedText
                style={[
                  styles.tabText,
                  activeTab === "found" && styles.activeTabText,
                ]}
              >
                {t("home.foundTab")}
              </ThemedText>
            </Pressable>
          </View>

          {/* Sort, filter, and search */}
          <View style={styles.toolbar}>
            <Pressable
              onPress={() => {
                setSortMode((current) =>
                  current === "newest" ? "candidates" : "newest",
                );
                setSourceMenuOpen(false);
                setFilterOpen(false);
              }}
              accessibilityRole="button"
              accessibilityLabel={
                sortMode === "newest"
                  ? t("home.sortCandidates")
                  : t("home.sortNewest")
              }
              style={({ pressed }) => [
                styles.toolButton,
                sortMode === "candidates" && styles.activeToolButton,
                pressed && styles.pressed,
              ]}
            >
              <ThemedText style={styles.sortIcon}>↕</ThemedText>

              <ThemedText type="small" style={styles.toolText}>
                {sortMode === "newest"
                  ? t("home.newest")
                  : t("home.candidates")}
              </ThemedText>
            </Pressable>

            <Pressable
              onPress={() => {
                setFilterOpen((current) => !current);
                setSourceMenuOpen(false);
              }}
              accessibilityRole="button"
              accessibilityLabel={t("home.filter")}
              style={({ pressed }) => [
                styles.toolButton,
                hasPostFilters(filters) && styles.activeToolButton,
                pressed && styles.pressed,
              ]}
            >
              <View style={styles.filterIcon}>
                <View style={styles.filterLine}>
                  <View style={styles.filterKnobLeft} />
                </View>
                <View style={styles.filterLine}>
                  <View style={styles.filterKnobRight} />
                </View>
              </View>

              <ThemedText type="small" style={styles.toolText}>
                {t("home.filter")}
              </ThemedText>
            </Pressable>

            <View style={styles.searchBox}>
              <View style={styles.searchIcon}>
                <View style={styles.searchCircle} />
                <View style={styles.searchHandle} />
              </View>

              <TextInput
                style={styles.searchInput}
                placeholder={t("home.searchPlaceholder")}
                placeholderTextColor="#9A9DA3"
                value={filters.q ?? ""}
                onChangeText={q => setFilters(current => ({ ...current, q }))}
                maxLength={100}
                autoCapitalize="none"
                autoCorrect={false}
                returnKeyType="search"
                onSubmitEditing={() => Keyboard.dismiss()}
                accessibilityLabel={t("home.searchAccessibility")}
              />
            </View>
          </View>

          {filterOpen ? (
            <PostFilterDialog initial={filters} categories={categories}
              postType={activeTab === "lost" ? "LOST" : "FOUND"}
              onApply={next => { setFilters(next); setFilterOpen(false); }}
              onClose={() => setFilterOpen(false)} />
          ) : null}

          {sortMode === "candidates" ? (
            <View style={styles.sourceArea}>
              <Pressable
                accessibilityRole="button"
                accessibilityLabel={t("home.selectSource")}
                onPress={() => {
                  setSourceMenuOpen((current) => !current);
                  setFilterOpen(false);
                }}
                style={styles.sourceButton}
              >
                <ThemedText type="small" style={styles.sourceLabel}>
                  {activeTab === "lost"
                    ? t("home.myFoundPost")
                    : t("home.myLostPost")}
                </ThemedText>
                <ThemedText
                  type="small"
                  numberOfLines={1}
                  style={styles.sourceTitle}
                >
                  {selectedSource?.title ?? t("home.selectSource")}
                </ThemedText>
                <ThemedText type="small">
                  {sourceMenuOpen ? "⌃" : "⌄"}
                </ThemedText>
              </Pressable>
              {sourceMenuOpen ? (
                <View style={styles.choicePanel}>
                  {sourcesLoading ? (
                    <ThemedText type="small">{t("common.loading")}</ThemedText>
                  ) : null}
                  {sourceError ? (
                    <ThemedText type="small" style={styles.errorText}>
                      {sourceError}
                    </ThemedText>
                  ) : null}
                  {!user ? (
                    <ThemedText type="small">
                      {t("common.loginRequired")}
                    </ThemedText>
                  ) : null}
                  {!sourcesLoading &&
                  !sourceError &&
                  user &&
                  sources.length === 0 ? (
                    <ThemedText type="small">
                      {t("home.noSourcePosts")}
                    </ThemedText>
                  ) : null}
                  <ScrollView style={styles.sourceOptions} nestedScrollEnabled>
                    {user
                      ? sources.map((post) => (
                          <Pressable
                            key={post.id}
                            accessibilityRole="button"
                            onPress={() => {
                              setSelectedSourceIds((current) => ({
                                ...current,
                                [activeTab]: post.id,
                              }));
                              setSourceMenuOpen(false);
                            }}
                            style={[
                              styles.sourceOption,
                              selectedSourceIds[activeTab] === post.id &&
                                styles.selectedChoice,
                            ]}
                          >
                            <ThemedText type="small" numberOfLines={1}>
                              {post.title}
                            </ThemedText>
                          </Pressable>
                        ))
                      : null}
                  </ScrollView>
                </View>
              ) : null}
            </View>
          ) : null}

          {/* Post list */}
          <View
            style={styles.boardArea}
            accessibilityLabel={
              activeTab === "lost" ? t("home.lostBoard") : t("home.foundBoard")
            }
          >
            {(["lost", "found"] as const).map((tab) =>
              activeTab === tab || visitedBoards.includes(tab) ? (
                <View
                  key={`${tab}-${params.refresh ?? ""}`}
                  style={{ flex: 1, display: activeTab === tab ? "flex" : "none" }}
                  accessibilityElementsHidden={activeTab !== tab}
                  importantForAccessibility={activeTab === tab ? "auto" : "no-hide-descendants"}
                >
                  <PostBoard
                    type={tab === "lost" ? "LOST" : "FOUND"}
                    filters={filters}
                    sortMode={sortMode}
                    sourcePostId={selectedSourceIds[tab]}
                    active={activeTab === tab}
                  />
                </View>
              ) : null,
            )}
          </View>

          <CreatePostButton />
        </View>
      </SafeAreaView>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    flex: 1,
    backgroundColor: "#FFFFFF",
  },
  safeArea: {
    flex: 1,
    width: "100%",
    maxWidth: MaxContentWidth,
    alignSelf: "center",
  },
  content: { flex: 1 },

  header: {
    marginBottom: 30,
  },
  logo: {
    color: "#111111",
    fontSize: 23,
    lineHeight: 32,
    letterSpacing: -0.7,
  },
  settingsButton: {
    width: 44,
    height: 44,
    alignItems: "center",
    justifyContent: "center",
  },
  headerActions: {
    flexDirection: "row",
    alignItems: "center",
    gap: 2,
  },
  settingsIcon: {
    color: "#30353A",
    fontSize: 29,
    lineHeight: 36,
  },

  tabs: {
    flexDirection: "row",
    gap: 18,
    borderBottomWidth: 1,
    borderBottomColor: "#EEEEEF",
  },
  tab: {
    paddingTop: 4,
    paddingBottom: 12,
    borderBottomWidth: 2,
    borderBottomColor: "transparent",
    marginBottom: -1,
  },
  activeTab: {
    borderBottomColor: "#111111",
  },
  tabText: {
    color: "#9A9DA3",
    fontSize: 17,
    lineHeight: 26,
  },
  activeTabText: {
    color: "#111111",
  },

  toolbar: {
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
    marginTop: 16,
  },
  toolButton: {
    height: 42,
    paddingHorizontal: 12,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: "#DDDEE0",
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 6,
  },
  toolText: {
    color: "#222222",
  },
  activeToolButton: {
    backgroundColor: Colors.softgreen,
    borderColor: Colors.softgreen,
  },
  sortIcon: {
    color: "#30353A",
    fontSize: 19,
    lineHeight: 24,
  },

  filterIcon: {
    width: 15,
    height: 16,
    justifyContent: "space-evenly",
  },
  filterLine: {
    height: 1.5,
    backgroundColor: "#30353A",
    justifyContent: "center",
  },
  filterKnobLeft: {
    position: "absolute",
    left: 3,
    width: 5,
    height: 5,
    borderRadius: 3,
    borderWidth: 1.5,
    borderColor: "#30353A",
    backgroundColor: "#FFFFFF",
  },
  filterKnobRight: {
    position: "absolute",
    right: 2,
    width: 5,
    height: 5,
    borderRadius: 3,
    borderWidth: 1.5,
    borderColor: "#30353A",
    backgroundColor: "#FFFFFF",
  },

  searchBox: {
    flex: 1,
    minWidth: 0,
    height: 42,
    borderRadius: 24,
    borderWidth: 1,
    borderColor: "#DDDEE0",
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 12,
    gap: 8,
  },
  searchIcon: {
    width: 18,
    height: 20,
  },
  searchCircle: {
    position: "absolute",
    top: 1,
    left: 0,
    width: 14,
    height: 14,
    borderRadius: 7,
    borderWidth: 1.7,
    borderColor: "#30353A",
  },
  searchHandle: {
    position: "absolute",
    top: 13,
    left: 12,
    width: 7,
    height: 1.7,
    borderRadius: 1,
    backgroundColor: "#30353A",
    transform: [{ rotate: "45deg" }],
  },
  searchInput: {
    flex: 1,
    minWidth: 0,
    height: "100%",
    paddingVertical: 0,
    color: "#222222",
    fontSize: 13,
    fontFamily: Fonts.pretendardMedium,
  },

  choicePanel: {
    marginTop: 8,
    padding: 12,
    borderWidth: 1,
    borderColor: "#DDDEE0",
    borderRadius: 14,
    backgroundColor: "#FFFFFF",
    gap: 8,
  },
  panelTitle: { color: "#555555" },
  filterOptions: { flexDirection: "row", flexWrap: "wrap", gap: 8 },
  choiceChip: {
    borderWidth: 1,
    borderColor: "#DDDEE0",
    borderRadius: 16,
    paddingHorizontal: 10,
    paddingVertical: 7,
  },
  selectedChoice: {
    backgroundColor: Colors.softgreen,
    borderColor: Colors.primary,
  },
  sourceArea: { marginTop: 10 },
  sourceButton: {
    minHeight: 48,
    borderWidth: 1,
    borderColor: "#DDDEE0",
    borderRadius: 14,
    paddingHorizontal: 12,
    flexDirection: "row",
    alignItems: "center",
    gap: 8,
  },
  sourceLabel: { color: Colors.primary },
  sourceTitle: { flex: 1, color: "#222222" },
  sourceOptions: { maxHeight: 220 },
  sourceOption: { paddingVertical: 12, paddingHorizontal: 8 },
  errorText: { color: "#B54747" },
  boardArea: {
    flex: 1,
    marginTop: 20,
  },

  floatingButton: {
    position: "absolute",
    right: 24,
    bottom: BottomTabInset + 20,
    width: 64,
    height: 64,
    borderRadius: 32,
    backgroundColor: Colors.primary,
    alignItems: "center",
    justifyContent: "center",
    shadowColor: "#000000",
    shadowOffset: { width: 0, height: 4 },
    shadowOpacity: 0.12,
    shadowRadius: 8,
    elevation: 5,
  },
  plusHorizontal: {
    position: "absolute",
    width: 26,
    height: 1.5,
    borderRadius: 1,
    backgroundColor: "#FFFFFF",
  },
  plusVertical: {
    position: "absolute",
    width: 1.5,
    height: 26,
    borderRadius: 1,
    backgroundColor: "#FFFFFF",
  },
  floatingPressed: {
    opacity: 0.88,
    transform: [{ scale: 0.96 }],
  },
  pressed: {
    opacity: 0.6,
  },
});
