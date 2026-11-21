import { useCallback, useState } from "react";
import { useFocusEffect, useRouter } from "expo-router";
import {
  ActivityIndicator,
  Image,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import Svg, { Path } from "react-native-svg";
import Animated, {
  Easing,
  useAnimatedStyle,
  useSharedValue,
  withTiming,
} from "react-native-reanimated";

import { Colors, Fonts } from "@/constants/theme";
import { useLocale } from "@/i18n/LocaleProvider";
import { ApiError } from "@/lib/auth-api";
import { imageUrl, postsApi, type Category, type Post } from "@/lib/posts-api";

const transition = { duration: 280, easing: Easing.inOut(Easing.cubic) };

type PostDetails = {
  post: Post;
  category: Category | undefined;
  photo: string | null;
};

export default function ChatPostCard({
  postId, title, deleted = false,
}: { postId: string | null; title: string; deleted?: boolean }) {
  if (deleted || postId === null) return <DeletedChatPost />;
  return <AvailableChatPost postId={postId} title={title} />;
}

function DeletedChatPost() {
  const { t } = useLocale();
  return <View style={{ paddingHorizontal: 24, paddingVertical: 20 }}>
    <Text style={styles.title}>{t("chat.deletedPost")}</Text>
  </View>;
}

function AvailableChatPost({
  postId,
  title,
}: {
  postId: string;
  title: string;
}) {
  const router = useRouter();
  const { t, locale, categoryLabel } = useLocale();
  const [expanded, setExpanded] = useState(true);
  const [measured, setMeasured] = useState(false);
  const contentHeight = useSharedValue(0);
  const visibleHeight = useSharedValue(0);
  const open = useSharedValue(1);
  const contentStyle = useAnimatedStyle(() => ({
    height: measured ? visibleHeight.value : undefined,
    opacity: withTiming(open.value, transition),
  }));
  const arrowStyle = useAnimatedStyle(() => ({
    transform: [
      { rotate: `${withTiming((1 - open.value) * 180, transition)}deg` },
    ],
  }));
  const toggleExpanded = () => {
    if (!measured) return;
    const next = !expanded;
    setExpanded(next);
    open.set(next ? 1 : 0);
    visibleHeight.set(withTiming(next ? contentHeight.get() : 0, transition));
  };
  const [details, setDetails] = useState<PostDetails | null>(null);
  const [loading, setLoading] = useState(true);
  const [failed, setFailed] = useState(false);
  const [unavailable, setUnavailable] = useState(false);
  const [imageFailed, setImageFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);

  useFocusEffect(
    useCallback(() => {
      let active = true;
      const load = async () => {
        setLoading(true);
        setFailed(false);
        setUnavailable(false);
        try {
          const post = await postsApi.detail(postId);
          const [images, categories] = await Promise.allSettled([
            postsApi.images(postId),
            post.category_id === null
              ? Promise.resolve<Category[]>([])
              : postsApi.categories(),
          ]);
          if (!active) return;
          setImageFailed(false);
          setDetails({
            post,
            category:
              categories.status === "fulfilled"
                ? categories.value.find((item) => item.id === post.category_id)
                : undefined,
            photo:
              images.status === "fulfilled" && images.value[0]
                ? imageUrl(images.value[0].content_url)
                : null,
          });
          setFailed(
            images.status === "rejected" || categories.status === "rejected",
          );
        } catch (error) {
          if (!active) return;
          setDetails(null);
          if (error instanceof ApiError && error.status === 404)
            setUnavailable(true);
          else setFailed(true);
        } finally {
          if (active) setLoading(false);
        }
      };
      void load();
      return () => {
        active = false;
      };
    }, [postId, attempt]),
  );

  const post = details?.post;
  const formatEventTime = (value: string) =>
    new Date(value).toLocaleString(locale === "en" ? "en-US" : "ko-KR", {
      hour: "2-digit",
      minute: "2-digit",
      hour12: false,
    });
  const eventTime = post?.event_start_at
    ? formatEventTime(post.event_start_at) +
      (post.event_end_at && post.event_end_at !== post.event_start_at
        ? ` – ${formatEventTime(post.event_end_at)}`
        : "")
    : t("chat.timeUnavailable");
  const metadata = [post?.location_text, eventTime]
    .filter(Boolean)
    .join("  ·  ");

  if (unavailable) return <DeletedChatPost />;

  return (
    <View>
      <Animated.View
        style={[styles.collapsible, contentStyle]}
        pointerEvents={expanded ? "auto" : "none"}
        accessibilityElementsHidden={!expanded}
        importantForAccessibility={expanded ? "auto" : "no-hide-descendants"}
      >
        <View
          style={measured ? styles.measuredContent : undefined}
          onLayout={({ nativeEvent }) => {
            const height = nativeEvent.layout.height;
            contentHeight.set(height);
            // Use natural layout on entry. Only a user toggle animates height.
            if (open.get() === 1) visibleHeight.set(height);
            setMeasured(true);
          }}
        >
          <Pressable
            accessibilityRole="button"
            disabled={unavailable}
            style={styles.post}
            onPress={() =>
              router.push({ pathname: "/post/[id]", params: { id: postId } })
            }
          >
            {details?.photo && !imageFailed ? (
              <Image
                source={{ uri: details.photo }}
                accessibilityLabel={t("board.photoAccessibility")}
                style={styles.photo}
                onError={() => setImageFailed(true)}
              />
            ) : null}
            <View style={styles.copy}>
              {post ? (
                <View style={styles.tag}>
                  <Text style={styles.tagText}>
                    {details?.category
                      ? categoryLabel(
                          details.category.code,
                          details.category.name,
                        )
                      : post.category_id == null
                        ? t("chat.uncategorized")
                        : t("createPost.category")}
                  </Text>
                </View>
              ) : null}
              <Text numberOfLines={2} style={styles.title}>
                {post?.title ?? title}
              </Text>
              {metadata ? (
                <Text numberOfLines={2} style={styles.metadata}>
                  {metadata}
                </Text>
              ) : null}
            </View>
          </Pressable>
          {loading ? (
            <ActivityIndicator
              size="small"
              color={Colors.primary}
              style={styles.feedback}
            />
          ) : null}
          {unavailable ? (
            <Text style={[styles.feedbackText, styles.unavailable]}>
              {t("chat.postUnavailable")}
            </Text>
          ) : null}
          {failed || imageFailed ? (
            <Pressable
              accessibilityRole="button"
              onPress={() => setAttempt((value) => value + 1)}
              style={styles.feedback}
            >
              <Text accessibilityRole="alert" style={styles.feedbackText}>
                {t("chat.postDetailsFailed")} · {t("common.retry")}
              </Text>
            </Pressable>
          ) : null}
        </View>
      </Animated.View>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={t(
          expanded ? "chat.collapsePost" : "chat.expandPost",
        )}
        accessibilityState={{ expanded }}
        onPress={toggleExpanded}
        style={styles.toggle}
      >
        <Animated.View style={arrowStyle}>
          <Svg width={20} height={20} viewBox="0 0 24 24" fill="none">
            <Path
              d="M5 13l7-6 7 6M5 18l7-6 7 6"
              stroke="#C5C8C6"
              strokeWidth={1.4}
              strokeLinecap="round"
              strokeLinejoin="round"
            />
          </Svg>
        </Animated.View>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  collapsible: { overflow: "hidden" },
  measuredContent: { position: "absolute", top: 0, left: 0, right: 0 },
  post: {
    flexDirection: "row",
    alignItems: "center",
    gap: 26,
    paddingHorizontal: 24,
    paddingTop: 12,
    paddingBottom: 18,
  },
  copy: { flex: 1, minWidth: 0, alignItems: "flex-start", gap: 8 },
  tag: {
    backgroundColor: Colors.softgreen,
    borderRadius: 16,
    paddingHorizontal: 10,
    paddingVertical: 5,
  },
  tagText: {
    fontFamily: Fonts.pretendardMedium,
    fontSize: 13,
    color: "#171A19",
  },
  title: {
    fontFamily: Fonts.pretendardMedium,
    color: "#454A48",
    fontSize: 16,
    lineHeight: 23,
  },
  metadata: {
    fontFamily: Fonts.pretendardRegular,
    color: "#666C69",
    fontSize: 13,
    lineHeight: 20,
  },
  photo: {
    width: 100,
    height: 100,
    flexShrink: 0,
    borderRadius: 16,
    backgroundColor: "#E6E6E6",
  },
  feedback: {
    paddingHorizontal: 24,
    paddingBottom: 8,
    alignItems: "flex-start",
  },
  feedbackText: { color: "#87605B", fontSize: 12 },
  unavailable: { paddingHorizontal: 24, paddingBottom: 8 },
  toggle: {
    alignSelf: "center",
    alignItems: "center",
    justifyContent: "center",
    width: 64,
    height: 36,
  },
});
