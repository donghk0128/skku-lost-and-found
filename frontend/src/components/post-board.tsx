import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Image,
  Pressable,
  StyleSheet,
  Text,
  View,
  type ViewToken,
} from "react-native";
import ChevronDownIcon from "@/assets/icons/chevron-down.svg";
import type { PostFilters } from "@/lib/post-filters";
import { BottomTabInset, Colors, Fonts } from "@/constants/theme";
import {
  imageUrl,
  postsApi,
  type Category,
  type Post,
  type RecommendationReason,
} from "@/lib/posts-api";
import { useRouter } from "expo-router";
import { splitPostDescription } from "@/lib/post-description";
import { useAuth } from "@/providers/AuthProvider";
import { useLocale } from "@/i18n/LocaleProvider";
import type { TranslateFn } from "@/i18n";
import { readSession } from "@/lib/session-storage";

const boardViewabilityConfig = { itemVisiblePercentThreshold: 1 };

type BoardItem = {
  post: Post;
  rank?: number;
  reasons?: RecommendationReason[];
};

function relativeTime(date: string, t: TranslateFn) {
  const minutes = Math.max(
    0,
    Math.floor((Date.now() - new Date(date).getTime()) / 60000),
  );
  if (minutes < 1) return t("board.justNow");
  if (minutes < 60) return t("board.minutesAgo", { count: minutes });
  if (minutes < 1440)
    return t("board.hoursAgo", { count: Math.floor(minutes / 60) });
  return t("board.daysAgo", { count: Math.floor(minutes / 1440) });
}

export function PostRow({
  post,
  category,
  rank,
  reasons,
  showAuthor = true,
  showType = false,
}: {
  post: Post;
  category?: Category;
  rank?: number;
  reasons?: RecommendationReason[];
  showAuthor?: boolean;
  showType?: boolean;
}) {
  const { t, categoryLabel } = useLocale();
  const { user } = useAuth();
  const router = useRouter();
  const [thumbnail, setThumbnail] = useState<string | null>(null);
  const reasonLabels: Record<RecommendationReason, string> = {
    NEARBY_LOCATION: t("board.nearbyLocation"),
    OVERLAPPING_TIME: t("board.overlappingTime"),
    SAME_CATEGORY: t("board.sameCategory"),
    SIMILAR_MEANING: t("board.similarMeaning"),
  };
  useEffect(() => {
    let active = true;
    postsApi
      .images(post.id)
      .then((images) => {
        if (active)
          setThumbnail(images[0] ? imageUrl(images[0].content_url) : null);
      })
      .catch(() => {
        if (active) setThumbnail(null);
      });
    return () => {
      active = false;
    };
  }, [post.id]);
  return (
    <Pressable
      accessibilityRole="button"
      accessibilityLabel={post.title}
      onPress={() =>
        router.push({ pathname: "/post/[id]", params: { id: post.id } })
      }
      style={styles.row}
    >
      <View style={styles.copy}>
        {rank !== undefined ? (
          <Text style={styles.rank}>{t("board.rank", { rank })}</Text>
        ) : null}
        <Text numberOfLines={1} style={styles.title}>
          {post.title}
        </Text>
        <Text numberOfLines={1} style={styles.description}>
          {splitPostDescription(post.description).body}
        </Text>
        <View style={styles.meta}>
          {showType ? (
            <Text style={styles.badgeText}>
              {t(
                post.post_type === "LOST"
                  ? "post.lostBadge"
                  : "post.foundBadge",
              )}
            </Text>
          ) : null}
          {category ? (
            <View style={styles.badge}>
              <Text style={styles.badgeText}>
                {categoryLabel(category.code, category.name)}
              </Text>
            </View>
          ) : null}
          {showAuthor ? (
            <>
              <View style={styles.avatar} />
              <Text numberOfLines={1} style={styles.author}>
                {post.author_nickname ??
                  (post.author_id === user?.id
                    ? user.nickname
                    : t("common.postAuthor"))}
              </Text>
            </>
          ) : null}
          <Text style={styles.time}>{relativeTime(post.created_at, t)}</Text>
        </View>
        {post.status === "COMPLETED" ? (
          <Text style={styles.completed}>{t("board.completed")}</Text>
        ) : null}
        {reasons && reasons.length > 0 ? (
          <View style={styles.reasons}>
            {reasons.map((reason) => (
              <Text key={reason} style={styles.reason}>
                {reasonLabels[reason]}
              </Text>
            ))}
          </View>
        ) : null}
      </View>
      {thumbnail ? (
        <Image
          source={{ uri: thumbnail }}
          style={styles.image}
          onError={() => setThumbnail(null)}
          accessibilityLabel={t("board.photoAccessibility")}
        />
      ) : null}
    </Pressable>
  );
}

export default function PostBoard({
  type,
  filters,
  sortMode,
  sourcePostId,
}: {
  type: "LOST" | "FOUND";
  filters: PostFilters;
  sortMode: "newest" | "candidates";
  sourcePostId: string | null;
}) {
  const { locale, t } = useLocale();
  const { user } = useAuth();
  const listRef = useRef<FlatList<BoardItem>>(null);
  const [showScrollTop, setShowScrollTop] = useState(false);
  const onViewableItemsChanged = useCallback(
    ({ viewableItems }: { viewableItems: ViewToken<BoardItem>[] }) => {
      const firstIndex = viewableItems[0]?.index;
      if (firstIndex != null) setShowScrollTop(firstIndex >= 3);
    },
    [],
  );
  const [query, setQuery] = useState(filters);
  const [posts, setPosts] = useState<BoardItem[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const requests = useRef({ generation: 0, busy: false });
  useEffect(() => {
    const timeout = setTimeout(() => setQuery(filters), 300);
    return () => clearTimeout(timeout);
  }, [filters]);
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
  const load = useCallback(
    async (offset: number) => {
      if (sortMode === "candidates" && !sourcePostId) {
        setPosts([]);
        setTotal(0);
        setLoading(false);
        return;
      }
      if (offset > 0 && requests.current.busy) return;
      const version =
        offset === 0
          ? ++requests.current.generation
          : requests.current.generation;
      requests.current.busy = true;
      setLoading(true);
      setError("");
      try {
        let result: { items: BoardItem[]; total: number };
        if (sortMode === "candidates" && sourcePostId) {
          const session = await readSession();
          if (!session) throw new Error(t("common.loginRequired"));
          const ranked = await postsApi.rankedCandidates(
            sourcePostId,
            query,
            offset,
            session.access_token,
          );
          result = {
            items: ranked.items.map(({ post, rank, reasons }) => ({
              post,
              rank,
              reasons,
            })),
            total: ranked.total,
          };
        } else {
          const newest = await postsApi.list(type, query, offset);
          result = {
            items: newest.items.map((post) => ({ post })),
            total: newest.total,
          };
        }
        if (version !== requests.current.generation) return;
        setPosts((current) =>
          offset === 0 ? result.items : [...current, ...result.items],
        );
        setTotal(result.total);
      } catch (error) {
        if (version === requests.current.generation)
          setError(
            error instanceof Error ? error.message : t("common.postLoadFailed"),
          );
      } finally {
        if (version === requests.current.generation) {
          requests.current.busy = false;
          setLoading(false);
        }
      }
    },
    [type, query, sortMode, sourcePostId, t],
  );
  useEffect(() => {
    const state = requests.current;
    const timeout = setTimeout(() => {
      listRef.current?.scrollToOffset({ offset: 0, animated: false });
      setShowScrollTop(false);
      setPosts([]);
      setTotal(0);
      void load(0);
    }, 0);
    return () => {
      clearTimeout(timeout);
      state.generation++;
      state.busy = false;
    };
  }, [load]);
  return (
    <View style={styles.board}>
      <FlatList
        ref={listRef}
        viewabilityConfig={boardViewabilityConfig}
        onViewableItemsChanged={onViewableItemsChanged}
        showsVerticalScrollIndicator={false}
        data={posts}
        extraData={locale}
        keyExtractor={(item) => item.post.id}
        renderItem={({ item }) => (
          <PostRow
            post={item.post}
            rank={item.rank}
            reasons={item.reasons}
            category={categories.find(
              (category) => category.id === item.post.category_id,
            )}
          />
        )}
        contentContainerStyle={styles.list}
        keyboardShouldPersistTaps="handled"
        refreshing={loading && posts.length > 0}
        onRefresh={() => void load(0)}
        onEndReached={() => {
          if (!error && posts.length > 0 && posts.length < total)
            void load(posts.length);
        }}
        onEndReachedThreshold={0.3}
        ListEmptyComponent={
          !loading && !error ? (
            <Text style={styles.empty}>
              {sortMode === "candidates" && !sourcePostId
                ? user
                  ? t("home.selectSourcePrompt")
                  : t("common.loginRequired")
                : query.q?.trim()
                  ? t("board.searchEmpty")
                  : type === "LOST"
                    ? t("board.lostEmpty")
                    : t("board.foundEmpty")}
            </Text>
          ) : null
        }
        ListFooterComponent={
          <View style={styles.feedback}>
            {loading ? (
              <ActivityIndicator color={Colors.primary} />
            ) : error ? (
              <>
                <Text style={styles.error} accessibilityRole="alert">
                  {error}
                </Text>
                <Pressable
                  accessibilityRole="button"
                  onPress={() => void load(posts.length)}
                >
                  <Text style={styles.retry}>{t("board.retry")}</Text>
                </Pressable>
              </>
            ) : null}
          </View>
        }
      />
      {showScrollTop ? (
        <Pressable
          accessibilityRole="button"
          accessibilityLabel={t("board.scrollToTop")}
          onPress={() =>
            listRef.current?.scrollToOffset({ offset: 0, animated: true })
          }
          style={({ pressed }) => [
            styles.scrollTop,
            pressed && { opacity: 0.75 },
          ]}
        >
          <View style={{ transform: [{ rotate: "180deg" }] }}>
            <ChevronDownIcon width={18} height={18} color={Colors.primary} />
          </View>
        </Pressable>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  board: { flex: 1 },
  scrollTop: {
    position: "absolute",
    top: 12,
    alignSelf: "center",
    alignItems: "center",
    justifyContent: "center",
    width: 40,
    height: 40,
    borderRadius: 20,
    backgroundColor: "white",
    borderWidth: 1,
    borderColor: "#E2EAE6",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.1,
    shadowRadius: 8,
    elevation: 4,
  },
  list: { flexGrow: 1, paddingBottom: BottomTabInset + 20 },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 16,
    paddingVertical: 24,
    borderBottomWidth: 1,
    borderBottomColor: "#E9E9E9",
  },
  copy: { flex: 1, minWidth: 0, gap: 12 },
  rank: {
    color: Colors.primary,
    fontSize: 12,
    fontFamily: Fonts.pretendardSemiBold,
  },
  title: {
    fontFamily: Fonts.pretendardRegular,
    fontSize: 18,
    color: "#111111",
    letterSpacing: 0.5,
  },
  description: {
    fontFamily: Fonts.pretendardRegular,
    fontSize: 14,
    color: "#090909",
  },
  meta: { flexDirection: "row", alignItems: "center", gap: 8 },
  badge: {
    paddingHorizontal: 10,
    paddingVertical: 5,
    borderRadius: 20,
    backgroundColor: Colors.softgreen,
    maxWidth: 100,
  },
  badgeText: {
    color: "#111111",
    fontSize: 12,
    fontFamily: Fonts.pretendardRegular,
  },
  avatar: {
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: "#D9D9D9",
  },
  author: {
    flexShrink: 1,
    color: "#555555",
    fontSize: 12,
    fontFamily: Fonts.pretendardRegular,
  },
  time: { color: "#333333", fontSize: 12, fontFamily: Fonts.pretendardRegular },
  completed: {
    fontSize: 12,
    color: Colors.primary,
    fontFamily: Fonts.pretendardMedium,
  },
  reasons: { flexDirection: "row", flexWrap: "wrap", gap: 6 },
  reason: {
    color: Colors.primary,
    backgroundColor: Colors.softgreen,
    borderRadius: 8,
    overflow: "hidden",
    paddingHorizontal: 8,
    paddingVertical: 5,
    fontSize: 11,
    fontFamily: Fonts.pretendardMedium,
  },
  image: {
    width: 100,
    height: 100,
    borderRadius: 16,
    backgroundColor: "#F5F5F5",
  },
  empty: {
    textAlign: "center",
    marginTop: 80,
    color: "#777777",
    fontFamily: Fonts.pretendardRegular,
  },
  feedback: { padding: 24, alignItems: "center", gap: 12 },
  error: {
    color: "#B54747",
    textAlign: "center",
    fontFamily: Fonts.pretendardRegular,
  },
  retry: {
    color: Colors.primary,
    padding: 10,
    fontFamily: Fonts.pretendardSemiBold,
  },
});
