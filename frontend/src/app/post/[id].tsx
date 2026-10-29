import { useEffect, useRef, useState } from "react";
import { useLocalSearchParams, useRouter } from "expo-router";
import {
  ActivityIndicator,
  Image,
  Modal,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from "react-native";
import Svg, { Path } from "react-native-svg";
import { SafeAreaView } from "react-native-safe-area-context";
import { Colors, Fonts } from "@/constants/theme";
import { imageUrl, postsApi, type Post } from "@/lib/posts-api";
import { readSession, writeSession } from "@/lib/session-storage";
import { authApi } from "@/lib/auth-api";
import { splitPostDescription } from "@/lib/post-description";
import { useAuth } from "@/providers/AuthProvider";
import MapView, { Marker, PROVIDER_GOOGLE } from "react-native-maps";

const formatDate = (value: string) =>
  new Date(value).toLocaleString("ko-KR", {
    year: "numeric",
    month: "long",
    day: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });

function Recommendation({ post }: { post: Post }) {
  const router = useRouter();
  const [photo, setPhoto] = useState<string | null>(null);
  useEffect(() => {
    let active = true;
    postsApi
      .images(post.id)
      .then((images) => {
        if (active && images[0]) setPhoto(imageUrl(images[0].content_url));
      })
      .catch(() => undefined);
    return () => {
      active = false;
    };
  }, [post.id]);
  return (
    <Pressable
      accessibilityRole="button"
      onPress={() =>
        router.push({ pathname: "/post/[id]", params: { id: post.id } })
      }
      style={styles.recommendation}
    >
      {photo ? (
        <Image
          source={{ uri: photo }}
          style={styles.recommendationImage}
          onError={() => setPhoto(null)}
        />
      ) : (
        <View style={[styles.recommendationImage, styles.placeholder]}>
          <Text style={styles.placeholderText}>사진 없음</Text>
        </View>
      )}
      <Text style={styles.recommendationTitle} numberOfLines={2}>
        {post.title}
      </Text>
      <Text style={styles.small}>
        {new Date(post.created_at).toLocaleDateString("ko-KR")}
      </Text>
    </Pressable>
  );
}

export default function PostDetailRoute() {
  const { id, refresh } = useLocalSearchParams<{
    id: string;
    refresh?: string;
  }>();
  return <PostDetail key={`${id}-${refresh ?? ""}`} id={id} />;
}

function PostDetail({ id }: { id: string }) {
  const router = useRouter();
  const { user } = useAuth();
  const width = Math.min(useWindowDimensions().width, 640);
  const [post, setPost] = useState<Post | null>(null);
  const [photos, setPhotos] = useState<string[]>([]);
  const [category, setCategory] = useState("");
  const [recommendations, setRecommendations] = useState<Post[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState("");
  const [photoError, setPhotoError] = useState(false);
  const [recommendationError, setRecommendationError] = useState(false);
  const [page, setPage] = useState(0);
  const [attempt, setAttempt] = useState(0);
  const moreButton = useRef<View>(null);
  const rootView = useRef<View>(null);
  const [menuAnchor, setMenuAnchor] = useState({ top: 64, right: 24 });
  const showMenu = () =>
    moreButton.current?.measureInWindow((x, y, buttonWidth, buttonHeight) => {
      rootView.current?.measureInWindow((rootX, rootY, rootWidth) => {
        setMenuAnchor({
          top: y - rootY + buttonHeight + 4,
          right: Math.max(16, rootWidth - (x - rootX) - buttonWidth),
        });
        setMenu("actions");
      });
    });
  const [menu, setMenu] = useState<"actions" | "delete" | null>(null);
  const [deleting, setDeleting] = useState(false);
  const [actionError, setActionError] = useState("");
  const pendingDelete = useRef(false);
  const remove = async () => {
    if (pendingDelete.current) return;
    pendingDelete.current = true;
    setDeleting(true);
    setActionError("");
    try {
      const session = await readSession();
      if (!session) throw new Error("로그인이 필요합니다.");
      const token = await authApi.refresh(session.refresh_token);
      session.access_token = token.access_token;
      await writeSession(session);
      await postsApi.delete(id, session.access_token);
      setMenu(null);
      router.dismissAll();
      router.replace({
        pathname: "/",
        params: {
          board: post?.post_type ?? "LOST",
          refresh: String(Date.now()),
        },
      });
    } catch (error) {
      setActionError(
        error instanceof Error ? error.message : "삭제하지 못했습니다.",
      );
    } finally {
      pendingDelete.current = false;
      setDeleting(false);
    }
  };
  useEffect(() => {
    let active = true;
    async function load() {
      try {
        const result = await postsApi.detail(id);
        if (!active) return;
        setPost(result);
        setLoading(false);
        const [images, categories, related] = await Promise.allSettled([
          postsApi.images(id),
          postsApi.categories(),
          postsApi.recommendations(id),
        ]);
        if (!active) return;
        if (images.status === "fulfilled")
          setPhotos(images.value.map((image) => imageUrl(image.content_url)));
        else setPhotoError(true);
        if (categories.status === "fulfilled")
          setCategory(
            categories.value.find((item) => item.id === result.category_id)
              ?.name ?? "",
          );
        if (related.status === "fulfilled")
          setRecommendations(related.value.items.map((item) => item.post));
        else setRecommendationError(true);
      } catch (error) {
        if (active) {
          setError(
            error instanceof Error
              ? error.message
              : "게시글을 불러오지 못했습니다.",
          );
          setLoading(false);
        }
      }
    }
    void load();
    return () => {
      active = false;
    };
  }, [id, attempt]);
  const retry = () => {
    setError("");
    setPhotoError(false);
    setRecommendationError(false);
    setAttempt((current) => current + 1);
  };
  const back = () => (router.canGoBack() ? router.back() : router.replace("/"));
  if (loading || !post)
    return (
      <SafeAreaView style={styles.root}>
        <Pressable
          onPress={back}
          style={styles.back}
          accessibilityLabel="뒤로가기"
        >
          <Text style={styles.backText}>‹</Text>
        </Pressable>
        <View style={styles.state}>
          {loading ? (
            <ActivityIndicator color={Colors.primary} />
          ) : (
            <>
              <Text style={styles.error}>{error}</Text>
              <Pressable onPress={retry}>
                <Text style={styles.link}>다시 시도</Text>
              </Pressable>
            </>
          )}
        </View>
      </SafeAreaView>
    );
  const lost = post.post_type === "LOST";
  const content = splitPostDescription(post.description);
  const details = [
    category ? ["카테고리", category] : null,
    content.features ? ["특징", content.features] : null,
    post.item_name ? ["물품명", post.item_name] : null,
    post.event_start_at && post.event_end_at
      ? [
          lost ? "분실 추정 시간" : "습득 시간",
          post.event_start_at === post.event_end_at
            ? formatDate(post.event_start_at)
            : `${formatDate(post.event_start_at)}\n~ ${formatDate(post.event_end_at)}`,
        ]
      : null,
    post.location_text
      ? [lost ? "분실 장소" : "습득 장소", post.location_text]
      : null,
  ].filter((item): item is string[] => item !== null);
  return (
    <SafeAreaView
      ref={rootView}
      style={styles.root}
      edges={["top", "left", "right"]}
    >
      <View style={[styles.header, { maxWidth: 640 }]}>
        <Pressable
          onPress={back}
          accessibilityRole="button"
          accessibilityLabel="뒤로가기"
          style={styles.back}
        >
          <Text style={styles.backText}>‹</Text>
        </Pressable>
        <Text style={styles.headerTitle}>
          {lost ? "분실물" : "습득물"} 상세
        </Text>
        {post.author_id === user?.id ? (
          <Pressable
            accessibilityRole="button"
            ref={moreButton}
            accessibilityLabel="게시글 더보기"
            onPress={showMenu}
            style={styles.back}
          >
            <Text style={styles.more}>⋮</Text>
          </Pressable>
        ) : (
          <View style={styles.back} />
        )}
      </View>
      <ScrollView contentContainerStyle={styles.content}>
        {photos.length ? (
          <View style={styles.hero}>
            <ScrollView
              key={`${id}-${attempt}`}
              horizontal
              pagingEnabled
              showsHorizontalScrollIndicator={false}
              onMomentumScrollEnd={(event) =>
                setPage(Math.round(event.nativeEvent.contentOffset.x / width))
              }
            >
              {photos.map((uri, index) => (
                <View
                  key={uri}
                  style={{ width, height: Math.min(width * 0.85, 420) }}
                >
                  <Image
                    source={{ uri }}
                    style={styles.heroImage}
                    resizeMode="cover"
                    accessibilityLabel={`물품 사진 ${index + 1}`}
                    onError={() => setPhotoError(true)}
                  />
                </View>
              ))}
            </ScrollView>
            <View style={styles.counter}>
              <Text style={styles.counterText}>
                {page + 1} / {photos.length}
              </Text>
            </View>
          </View>
        ) : null}
        {photoError ? (
          <Pressable onPress={retry} style={styles.photoFeedback}>
            <Text style={styles.small}>
              사진을 불러오지 못했습니다 · 다시 시도
            </Text>
          </Pressable>
        ) : null}
        <View style={styles.body}>
          <View style={styles.badges}>
            <View
              style={[
                styles.badge,
                lost ? styles.lostBadge : styles.foundBadge,
              ]}
            >
              <Text style={[styles.badgeText, !lost && styles.foundText]}>
                {lost ? "분실했어요" : "습득했어요"}
              </Text>
            </View>
            <View style={styles.statusBadge}>
              <Text style={styles.statusText}>
                {post.status === "OPEN"
                  ? lost
                    ? "찾는 중"
                    : "주인 찾는 중"
                  : "완료"}
              </Text>
            </View>
          </View>
          <Text style={styles.title}>{post.title}</Text>
          <View style={styles.authorRow}>
            <View style={styles.avatar}>
              <Text style={styles.avatarText}>
                {post.author_id === user?.id ? user.nickname.slice(0, 1) : "·"}
              </Text>
            </View>
            <View style={styles.authorCopy}>
              <Text style={styles.author}>
                {post.author_id === user?.id ? user.nickname : "작성자"}
              </Text>
              <Text style={styles.small}>{formatDate(post.created_at)}</Text>
            </View>
          </View>
          <View style={styles.divider} />
          <Text selectable style={styles.description}>
            {content.body}
          </Text>
          {details.length ? (
            <View style={styles.infoCard}>
              <Text style={styles.sectionTitle}>물품 정보</Text>
              {details.map(([label, value]) => (
                <View key={label} style={styles.infoRow}>
                  <Text style={styles.infoLabel}>{label}</Text>
                  <Text selectable style={styles.infoValue}>
                    {value}
                  </Text>
                </View>
              ))}
            </View>
          ) : null}
          {post.latitude !== null && post.longitude !== null ? (
            <MapView
              provider={PROVIDER_GOOGLE}
              style={{ height: 200 }}
              scrollEnabled={false}
              initialRegion={{
                latitude: post.latitude ?? 0,
                longitude: post.longitude ?? 0,
                latitudeDelta: 0.005,
                longitudeDelta: 0.005,
              }}
            >
              <Marker
                coordinate={{
                  latitude: post.latitude ?? 0,
                  longitude: post.longitude ?? 0,
                }}
              />
            </MapView>
          ) : null}
        </View>
        {recommendations.length || recommendationError ? (
          <View style={styles.related}>
            <View style={styles.sectionHeader}>
              <Text style={styles.sectionTitle}>
                비슷한 {lost ? "습득물" : "분실물"}
              </Text>
              <Text style={styles.small}>혹시 이 물건인가요?</Text>
            </View>
            {recommendationError ? (
              <Pressable onPress={retry}>
                <Text style={styles.link}>
                  추천을 불러오지 못했습니다 · 다시 시도
                </Text>
              </Pressable>
            ) : (
              <ScrollView
                horizontal
                showsHorizontalScrollIndicator={false}
                contentContainerStyle={styles.cards}
              >
                {recommendations.map((item) => (
                  <Recommendation key={item.id} post={item} />
                ))}
              </ScrollView>
            )}
          </View>
        ) : null}
      </ScrollView>
      {menu === "actions" ? (
        <View style={styles.popoverLayer}>
          <Pressable
            style={StyleSheet.absoluteFill}
            onPress={() => setMenu(null)}
            accessibilityLabel="메뉴 닫기"
          />
          <View
            style={[
              styles.popover,
              { top: menuAnchor.top, right: menuAnchor.right },
            ]}
            accessibilityViewIsModal
          >
            <Pressable
              accessibilityRole="button"
              style={styles.popoverItem}
              onPress={() => {
                setMenu(null);
                router.push({
                  pathname: "/create-post",
                  params: { type: post.post_type, editId: id },
                });
              }}
            >
              <Svg
                width={17}
                height={17}
                viewBox="0 0 24 24"
                fill="none"
                stroke="#555555"
                strokeWidth={1.6}
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <Path d="m16 3 5 5M3 21l5-1L21 7a2.1 2.1 0 0 0-5-5L3 15z" />
              </Svg>
              <Text style={styles.popoverText}>수정하기</Text>
            </Pressable>
            <Pressable
              accessibilityRole="button"
              style={styles.popoverItem}
              onPress={() => {
                setActionError("");
                setMenu("delete");
              }}
            >
              <Svg
                width={17}
                height={17}
                viewBox="0 0 24 24"
                fill="none"
                stroke="#555555"
                strokeWidth={1.6}
                strokeLinecap="round"
                strokeLinejoin="round"
              >
                <Path d="M3 6h18M9 6V3h6v3M5 6l1 15h12l1-15M10 10v7M14 10v7" />
              </Svg>
              <Text style={styles.popoverText}>삭제하기</Text>
            </Pressable>
          </View>
        </View>
      ) : null}
      <Modal
        visible={menu === "delete"}
        transparent
        animationType="none"
        onRequestClose={() => {
          if (!deleting) setMenu(null);
        }}
      >
        <View style={styles.menuOverlay}>
          <Pressable
            style={StyleSheet.absoluteFill}
            disabled={deleting}
            onPress={() => setMenu(null)}
            accessibilityLabel="닫기"
          />
          <View style={styles.menuCard}>
            <Text style={styles.confirmTitle}>게시글을 삭제할까요?</Text>
            <Text style={styles.confirmHint}>
              삭제한 게시글은 목록에서 더 이상 표시되지 않습니다.
            </Text>
            {actionError ? (
              <Text style={styles.confirmError}>{actionError}</Text>
            ) : null}
            <View style={styles.confirmActions}>
              <Pressable
                disabled={deleting}
                style={styles.menuItem}
                onPress={() => void remove()}
              >
                <Text style={styles.deleteText}>
                  {deleting ? "삭제 중…" : "삭제하기"}
                </Text>
              </Pressable>
              <Pressable
                disabled={deleting}
                style={styles.menuItem}
                onPress={() => setMenu(null)}
              >
                <Text style={styles.confirmHint}>취소</Text>
              </Pressable>
            </View>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}
const styles = StyleSheet.create({
  popoverLayer: {
    position: "absolute",
    top: 0,
    right: 0,
    bottom: 0,
    left: 0,
    zIndex: 100,
  },
  confirmTitle: {
    fontSize: 16,
    fontFamily: Fonts.pretendardSemiBold,
    color: "#222",
  },
  confirmHint: {
    fontSize: 12,
    lineHeight: 18,
    fontFamily: Fonts.pretendardRegular,
    color: "#777",
  },
  confirmError: { fontSize: 12, lineHeight: 18, color: "#555" },
  confirmActions: { flexDirection: "row", gap: 12 },
  popover: {
    position: "absolute",
    width: 144,
    paddingVertical: 0,
    backgroundColor: "white",
    borderWidth: 1,
    borderColor: "#E5E5E5",
    borderRadius: 10,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 2 },
    shadowOpacity: 0.07,
    shadowRadius: 6,
    elevation: 3,
  },
  popoverItem: {
    minHeight: 40,
    flexDirection: "row",
    alignItems: "center",
    gap: 9,
    paddingHorizontal: 14,
  },
  popoverText: {
    fontSize: 14,
    fontFamily: Fonts.pretendardMedium,
    color: "#222",
  },
  more: { fontSize: 30, color: "#333" },
  menuOverlay: {
    flex: 1,
    backgroundColor: "rgba(0,0,0,0.4)",
    justifyContent: "center",
    padding: 28,
  },
  menuCard: {
    width: "100%",
    maxWidth: 320,
    alignSelf: "center",
    backgroundColor: "white",
    borderRadius: 14,
    padding: 18,
    gap: 10,
  },
  menuItem: {
    flex: 1,
    minHeight: 40,
    alignItems: "center",
    justifyContent: "center",
    borderTopWidth: 1,
    borderColor: "#F0F0F0",
  },
  menuText: {
    color: Colors.primary,
    fontFamily: Fonts.pretendardMedium,
    fontSize: 16,
  },
  deleteText: {
    color: "#222",
    fontFamily: Fonts.pretendardMedium,
    fontSize: 14,
  },
  root: { flex: 1, backgroundColor: "#FFF" },
  header: {
    width: "100%",
    alignSelf: "center",
    height: 58,
    paddingHorizontal: 16,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
  back: {
    width: 44,
    height: 44,
    alignItems: "center",
    justifyContent: "center",
  },
  backText: { color: "#222", fontSize: 34 },
  headerTitle: {
    fontFamily: Fonts.pretendardMedium,
    fontSize: 16,
    color: "#333",
  },
  content: {
    width: "100%",
    maxWidth: 640,
    alignSelf: "center",
    paddingBottom: 48,
  },
  hero: { backgroundColor: "#F6F8F7" },
  heroImage: { width: "100%", height: "100%" },
  counter: {
    position: "absolute",
    bottom: 16,
    right: 24,
    paddingHorizontal: 12,
    paddingVertical: 6,
    borderRadius: 20,
    backgroundColor: "rgba(0,0,0,0.5)",
  },
  counterText: {
    color: "white",
    fontSize: 12,
    fontFamily: Fonts.pretendardMedium,
  },
  body: { padding: 24, gap: 20 },
  badges: { flexDirection: "row", gap: 8 },
  badge: { paddingHorizontal: 12, paddingVertical: 7, borderRadius: 9 },
  lostBadge: { backgroundColor: Colors.softgreen },
  foundBadge: { backgroundColor: Colors.softblue },
  badgeText: {
    color: Colors.primary,
    fontFamily: Fonts.pretendardSemiBold,
    fontSize: 12,
  },
  foundText: { color: "#4D6B9D" },
  statusBadge: {
    backgroundColor: "#F3F4F3",
    paddingHorizontal: 12,
    paddingVertical: 7,
    borderRadius: 9,
  },
  statusText: {
    color: "#777",
    fontSize: 12,
    fontFamily: Fonts.pretendardMedium,
  },
  title: {
    fontFamily: Fonts.pretendardSemiBold,
    fontSize: 25,
    lineHeight: 35,
    letterSpacing: -0.6,
    color: "#17251F",
  },
  authorRow: { flexDirection: "row", alignItems: "center", gap: 11 },
  avatar: {
    width: 36,
    height: 36,
    borderRadius: 18,
    backgroundColor: "#EDF2EF",
    alignItems: "center",
    justifyContent: "center",
  },
  avatarText: { color: Colors.primary, fontFamily: Fonts.pretendardMedium },
  authorCopy: { gap: 5 },
  author: { fontFamily: Fonts.pretendardMedium, fontSize: 13, color: "#444" },
  small: {
    fontFamily: Fonts.pretendardRegular,
    fontSize: 12,
    color: "#8C9690",
    lineHeight: 18,
  },
  divider: { height: 1, backgroundColor: "#EDF0EE", marginVertical: 4 },
  description: {
    color: "#3D4741",
    fontFamily: Fonts.pretendardRegular,
    fontSize: 16,
    lineHeight: 28,
  },
  infoCard: {
    marginTop: 12,
    backgroundColor: "#F7F9F8",
    padding: 20,
    borderRadius: 20,
    gap: 20,
  },
  sectionTitle: {
    fontFamily: Fonts.pretendardSemiBold,
    fontSize: 17,
    color: "#23382C",
  },
  infoRow: { flexDirection: "row", alignItems: "flex-start", gap: 16 },
  infoLabel: {
    width: 88,
    fontFamily: Fonts.pretendardRegular,
    color: "#8A938D",
    fontSize: 13,
    lineHeight: 22,
  },
  infoValue: {
    flex: 1,
    color: "#3E4B43",
    fontFamily: Fonts.pretendardMedium,
    fontSize: 14,
    lineHeight: 22,
  },
  related: {
    marginTop: 12,
    borderTopWidth: 8,
    borderColor: "#F7F9F8",
    paddingTop: 28,
    gap: 18,
  },
  sectionHeader: { paddingHorizontal: 24, gap: 6 },
  cards: { paddingHorizontal: 24, gap: 14 },
  recommendation: { width: 140, gap: 8 },
  recommendationImage: { width: 140, height: 125, borderRadius: 16 },
  placeholder: {
    backgroundColor: "#F1F4F2",
    alignItems: "center",
    justifyContent: "center",
  },
  placeholderText: { color: "#9BA49F", fontSize: 12 },
  recommendationTitle: {
    fontFamily: Fonts.pretendardMedium,
    color: "#333",
    fontSize: 14,
    lineHeight: 20,
  },
  state: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: 28,
    gap: 20,
  },
  error: { color: "#B54747", textAlign: "center" },
  link: {
    color: Colors.primary,
    padding: 16,
    fontFamily: Fonts.pretendardMedium,
  },
  photoFeedback: { padding: 16, alignItems: "center" },
});
