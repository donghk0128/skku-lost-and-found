import { useCallback, useEffect, useRef, useState } from "react";
import {
  ActivityIndicator,
  FlatList,
  Image,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { BottomTabInset, Colors, Fonts } from "@/constants/theme";
import { imageUrl, postsApi, type Category, type Post } from "@/lib/posts-api";
import { useFocusEffect, useRouter } from "expo-router";
import { splitPostDescription } from "@/lib/post-description";
import { useAuth } from "@/providers/AuthProvider";

function relativeTime(date: string) {
  const minutes = Math.max(
    0,
    Math.floor((Date.now() - new Date(date).getTime()) / 60000),
  );
  if (minutes < 1) return "방금 전";
  if (minutes < 60) return `${minutes}분 전`;
  if (minutes < 1440) return `${Math.floor(minutes / 60)}시간 전`;
  return `${Math.floor(minutes / 1440)}일 전`;
}

function PostRow({ post, category }: { post: Post; category?: string }) {
  const { user } = useAuth();
  const router = useRouter();
  const [thumbnail, setThumbnail] = useState<string | null>(null);
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
        <Text numberOfLines={1} style={styles.title}>
          {post.title}
        </Text>
        <Text numberOfLines={1} style={styles.description}>
          {splitPostDescription(post.description).body}
        </Text>
        <View style={styles.meta}>
          {category ? (
            <View style={styles.badge}>
              <Text style={styles.badgeText}>{category}</Text>
            </View>
          ) : null}
          <View style={styles.avatar} />
          <Text numberOfLines={1} style={styles.author}>
            {post.author_id === user?.id ? user.nickname : "작성자"}
          </Text>
          <Text style={styles.time}>{relativeTime(post.created_at)}</Text>
        </View>
        {post.status === "COMPLETED" ? (
          <Text style={styles.completed}>완료</Text>
        ) : null}
      </View>
      {thumbnail ? (
        <Image
          source={{ uri: thumbnail }}
          style={styles.image}
          onError={() => setThumbnail(null)}
          accessibilityLabel="게시글 사진"
        />
      ) : null}
    </Pressable>
  );
}

export default function PostBoard({
  type,
  search,
}: {
  type: "LOST" | "FOUND";
  search: string;
}) {
  const [query, setQuery] = useState(search);
  const [posts, setPosts] = useState<Post[]>([]);
  const [categories, setCategories] = useState<Category[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const requests = useRef({ generation: 0, busy: false });
  useEffect(() => {
    const timeout = setTimeout(() => setQuery(search), 300);
    return () => clearTimeout(timeout);
  }, [search]);
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
      if (offset > 0 && requests.current.busy) return;
      const version =
        offset === 0
          ? ++requests.current.generation
          : requests.current.generation;
      requests.current.busy = true;
      setLoading(true);
      setError("");
      try {
        const result = await postsApi.list(type, query, offset);
        if (version !== requests.current.generation) return;
        setPosts((current) =>
          offset === 0 ? result.items : [...current, ...result.items],
        );
        setTotal(result.total);
      } catch (error) {
        if (version === requests.current.generation)
          setError(
            error instanceof Error
              ? error.message
              : "게시글을 불러오지 못했습니다.",
          );
      } finally {
        if (version === requests.current.generation) {
          requests.current.busy = false;
          setLoading(false);
        }
      }
    },
    [type, query, requests],
  );
  useFocusEffect(
    useCallback(() => {
      const state = requests.current;
      const timeout = setTimeout(() => {
        setPosts([]);
        setTotal(0);
        void load(0);
      }, 0);
      return () => {
        clearTimeout(timeout);
        state.generation++;
        state.busy = false;
      };
    }, [load, requests]),
  );
  return (
    <FlatList
      data={posts}
      keyExtractor={(post) => post.id}
      renderItem={({ item }) => (
        <PostRow
          post={item}
          category={
            categories.find((category) => category.id === item.category_id)
              ?.name
          }
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
            {query.trim()
              ? "검색 결과가 없습니다."
              : type === "LOST"
                ? "등록된 분실물이 없습니다."
                : "등록된 습득물이 없습니다."}
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
                <Text style={styles.retry}>다시 시도</Text>
              </Pressable>
            </>
          ) : null}
        </View>
      }
    />
  );
}

const styles = StyleSheet.create({
  list: { flexGrow: 1, paddingBottom: BottomTabInset + 100 },
  row: {
    flexDirection: "row",
    alignItems: "center",
    gap: 16,
    paddingVertical: 24,
    borderBottomWidth: 1,
    borderBottomColor: "#E9E9E9",
  },
  copy: { flex: 1, minWidth: 0, gap: 12 },
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
