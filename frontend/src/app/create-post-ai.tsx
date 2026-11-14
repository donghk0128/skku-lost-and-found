import { useRef, useState } from "react";
import { useLocalSearchParams, useRouter } from "expo-router";
import * as ImagePicker from "expo-image-picker";
import {
  Image,
  Keyboard,
  Modal,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import Svg, { Circle, Path, Rect } from "react-native-svg";
import { SafeAreaView, useSafeAreaInsets } from "react-native-safe-area-context";

import { Colors, Fonts } from "@/constants/theme";
import { aiApi, type AIDraft } from "@/lib/ai-api";
import ChatLocationPicker from "@/components/ChatLocationPicker";
import { authApi } from "@/lib/auth-api";
import { postsApi, type PostImageAsset } from "@/lib/posts-api";
import type { PickedLocation } from "@/lib/location-picker";
import { joinPostDescription } from "@/lib/post-description";
import { readSession, writeSession } from "@/lib/session-storage";
import { useLocale } from "@/i18n/LocaleProvider";

function AttachmentIcon({ camera = false }: { camera?: boolean }) {
  return (
    <Svg width={24} height={24} viewBox="0 0 24 24" fill="none" stroke="#666" strokeWidth={1.7} strokeLinecap="round" strokeLinejoin="round">
      {camera ? (
        <>
          <Path d="M8 5 9.5 3h5L16 5h3a2 2 0 0 1 2 2v12a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V7a2 2 0 0 1 2-2Z" />
          <Circle cx={12} cy={13} r={4} />
        </>
      ) : (
        <>
          <Rect x={3} y={3} width={18} height={18} rx={3} />
          <Circle cx={8} cy={8} r={1.5} />
          <Path d="m3 17 5-5 4 4 4-6 5 7" />
        </>
      )}
    </Svg>
  );
}

type ChatMessage = {
  role: "user" | "assistant";
  content: string;
  showLocationPicker?: boolean;
};

export default function CreatePostAiScreen() {
  const { locale, t, categoryLabel } = useLocale();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [photoSheetOpen, setPhotoSheetOpen] = useState(false);
  const pendingPhotoSource = useRef<"camera" | "library" | null>(null);
  const scrollRef = useRef<ScrollView>(null);
  const locationPickerShown = useRef(false);
  const { type } = useLocalSearchParams<{ type?: string }>();
  const postType = type === "FOUND" ? "FOUND" : "LOST";
  const [message, setMessage] = useState("");
  const [messages, setMessages] = useState<ChatMessage[]>([
    {
      role: "assistant",
      content: t(
        postType === "LOST" ? "ai.initialPromptLost" : "ai.initialPromptFound",
      ),
    },
  ]);
  const [draft, setDraft] = useState<AIDraft | null>(null);
  const [pendingField, setPendingField] = useState<
    "item_name" | "location" | "event_time" | null
  >(null);
  const [collectedFields, setCollectedFields] = useState<
    Partial<Record<"item_name" | "location" | "event_time", string>>
  >({});
  const [confirmedLocation, setConfirmedLocation] =
    useState<PickedLocation | null>(null);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [error, setError] = useState("");
  const [photos, setPhotos] = useState<PostImageAsset[]>([]);
  const [savedPostId, setSavedPostId] = useState<string | null>(null);
  const features = draft?.keywords.join(", ") ?? "";

  const authenticatedToken = async () => {
    const session = await readSession();
    if (!session) throw new Error(t("common.loginRequired"));
    const refreshed = await authApi.refresh(session.refresh_token);
    session.access_token = refreshed.access_token;
    await writeSession(session);
    return session.access_token;
  };

  const continueChat = async (
    userMessages: { role: "user"; content: string }[],
    location = confirmedLocation,
    wasLocationAnswer = false,
  ) => {
    setBusy(true);
    setError("");
    try {
      const result = await aiApi.continueChat(
        {
          // 현재 화면 언어를 전달해 챗봇의 질문과 초안 언어를 일치시킨다.
          locale,
          post_type: postType,
          messages: userMessages,
          draft: draft ?? undefined,
          pending_field: pendingField,
          collected_fields: collectedFields,
          confirmed_location: location
            ? {
                text: location.address,
                latitude: location.latitude,
                longitude: location.longitude,
              }
            : undefined,
        },
        await authenticatedToken(),
      );
      setDraft(result.draft);
      setPendingField(result.pending_field);
      setCollectedFields(result.collected_fields);
      setReady(result.status === "READY");
      const shouldShowLocationPicker =
        !locationPickerShown.current &&
        (wasLocationAnswer ||
          Boolean(result.draft.location_text) ||
          result.draft.location_candidates.length > 0);
      if (shouldShowLocationPicker) locationPickerShown.current = true;
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: result.assistant_message,
          showLocationPicker: shouldShowLocationPicker,
        },
      ]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t("ai.responseFailed"));
    } finally {
      setBusy(false);
    }
  };

  const send = async () => {
    const content = message.trim();
    if (!content || busy || publishing) return;
    const location =
      pendingField === "location" && confirmedLocation?.address !== content
        ? null
        : confirmedLocation;
    if (location !== confirmedLocation) {
      setConfirmedLocation(null);
    }
    const nextMessages = [
      ...messages,
      {
        role: "user" as const,
        content,
      },
    ];
    const userMessages = nextMessages
      .filter(
        (item): item is { role: "user"; content: string } =>
          item.role === "user",
      )
      .slice(-12);
    setMessages(nextMessages);
    setMessage("");
    setReady(false);
    await continueChat(userMessages, location, pendingField === "location");
  };

  const confirmLocation = async (location: PickedLocation) => {
    if (busy || publishing) return;
    setConfirmedLocation(location);
    locationPickerShown.current = true;
    const userMessages = messages
      .filter(
        (item): item is { role: "user"; content: string } =>
          item.role === "user",
      )
      .slice(-12);
    await continueChat(userMessages, location);
  };

  const pickPhotos = async (source: "camera" | "library" = "library") => {
    if (busy || publishing || savedPostId || photos.length >= 5) return;
    try {
      if (source === "camera" && Platform.OS !== "web") {
        const permission = await ImagePicker.requestCameraPermissionsAsync();
        if (!permission.granted) {
          setError(t("ai.cameraPermission"));
          return;
        }
      }
      const result = source === "camera"
        ? await ImagePicker.launchCameraAsync({ mediaTypes: ["images"], quality: 0.8 })
        : await ImagePicker.launchImageLibraryAsync({
            mediaTypes: ["images"],
            allowsMultipleSelection: true,
            selectionLimit: 5 - photos.length,
            quality: 0.8,
          });
      if (result.canceled) return;
      if (
        result.assets.some(
          (asset) => asset.fileSize && asset.fileSize > 5 * 1024 * 1024,
        )
      ) {
        setError(t("createPost.photoTooLarge"));
        return;
      }
      if (
        result.assets.some(
          (asset) =>
            asset.mimeType &&
            !["image/jpeg", "image/png", "image/webp"].includes(asset.mimeType),
        )
      ) {
        setError(t("createPost.unsupportedPhoto"));
        return;
      }
      setPhotos((current) => [...current, ...result.assets].slice(0, 5));
      setError("");
    } catch {
      setError(t(source === "camera" ? "ai.cameraFailed" : "createPost.photoPermission"));
    }
  };

  const selectPhotoSource = (source: "camera" | "library") => {
    setPhotoSheetOpen(false);
    // iOS must dismiss the sheet before presenting the system camera/picker.
    if (Platform.OS === "ios") pendingPhotoSource.current = source;
    else void pickPhotos(source);
  };

  const removePhoto = (index: number) => {
    if (savedPostId || publishing) return;
    setPhotos((current) => current.filter((_, currentIndex) => currentIndex !== index));
    setError("");
  };

  const publish = async () => {
    if (!draft || !ready || publishing) return;
    setPublishing(true);
    setError("");
    let postId = savedPostId;
    try {
      const token = await authenticatedToken();
      if (!postId) {
        const post = await postsApi.createAiAssisted(
          {
            post_type: draft.post_type,
            title: draft.title,
            // 일반 작성과 같은 형식으로 AI 특징을 본문에 합쳐 저장한다.
            description: joinPostDescription(draft.description, features),
            item_name: draft.item_name ?? undefined,
            category_id: draft.category_id,
            location_text: draft.location_text ?? undefined,
            ...(confirmedLocation
              ? {
                  latitude: confirmedLocation.latitude,
                  longitude: confirmedLocation.longitude,
                }
              : draft.latitude !== null && draft.longitude !== null
                ? { latitude: draft.latitude, longitude: draft.longitude }
                : {}),
            event_start_at: draft.event_start_at ?? undefined,
            event_end_at: draft.event_end_at ?? undefined,
          },
          token,
        );
        postId = post.id;
        setSavedPostId(postId);
      }
      const uploadedImages = savedPostId
        ? await postsApi.images(postId)
        : [];
      for (let index = uploadedImages.length; index < photos.length; index++) {
        setError(
          t("createPost.uploadingPhoto", {
            current: index + 1,
            total: photos.length,
          }),
        );
        await postsApi.upload(postId, photos[index], token);
      }
      router.dismissAll();
      router.replace({ pathname: "/post/[id]", params: { id: postId } });
    } catch (cause) {
      setError(
        (postId ? `${t("createPost.uploadIncomplete")}\n` : "") +
          (cause instanceof Error ? cause.message : t("ai.publishFailed")),
      );
      setPublishing(false);
    }
  };

  const edit = () => {
    if (!draft) return;
    router.push({
      pathname: "/create-post",
      params: {
        type: draft.post_type,
        creationMethod: "AI_ASSISTED",
        title: draft.title,
        description: draft.description,
        features,
        categoryId: String(draft.category_id),
        place: draft.location_text ?? "",
        latitude: String(confirmedLocation?.latitude ?? draft.latitude ?? ""),
        longitude: String(
          confirmedLocation?.longitude ?? draft.longitude ?? "",
        ),
        startAt: draft.event_start_at ?? "",
        endAt: draft.event_end_at ?? "",
        photoAssets: JSON.stringify(
          photos.map(({ uri, fileName }) => ({ uri, fileName })),
        ),
      },
    });
  };

  return (
    <SafeAreaView style={styles.root}>
      <KeyboardAvoidingView
        style={styles.root}
        behavior={Platform.OS === "ios" ? "padding" : "height"}
      >
        <View style={styles.header}>
          <Pressable
            accessibilityLabel={t("common.back")}
            onPress={() => router.back()}
            style={styles.back}
          >
            <Text style={styles.backText}>‹</Text>
          </Pressable>
          <View>
            <Text style={styles.headerTitle}>{t("ai.title")}</Text>
            <Text style={styles.headerSubtitle}>{t("ai.subtitle")}</Text>
          </View>
          <View style={styles.back} />
        </View>
        <ScrollView
          ref={scrollRef}
          contentContainerStyle={styles.content}
          keyboardShouldPersistTaps="handled"
          onContentSizeChange={() =>
            scrollRef.current?.scrollToEnd({ animated: true })
          }
        >
          {messages.map((item, index) => (
            <View key={`${item.role}-${index}`} style={styles.messageGroup}>
              {item.showLocationPicker ? (
                <ChatLocationPicker
                  disabled={busy || publishing}
                  locationText={
                    draft?.location_text ?? draft?.location_candidates[0] ?? ""
                  }
                  onConfirm={(location) => void confirmLocation(location)}
                />
              ) : (
                <View
                  style={
                    item.role === "user"
                      ? styles.userBubble
                      : styles.assistantBubble
                  }
                >
                  <Text
                    style={
                      item.role === "user"
                        ? styles.userText
                        : styles.assistantText
                    }
                  >
                    {item.content}
                  </Text>
                </View>
              )}
            </View>
          ))}
          {busy ? (
            <View style={styles.assistantBubble}>
              <Text style={styles.assistantText}>
                {t("ai.organizingAnswer")}
              </Text>
            </View>
          ) : null}
          {ready && draft ? (
            <View style={styles.draftCard}>
              <Text style={styles.previewLabel}>{t("ai.preview")}</Text>
              <Text style={styles.draftTitle}>{draft.title}</Text>
              <Text style={styles.draftText}>{draft.description}</Text>
              <Text style={styles.draftMeta}>
                {t("createPost.features")}: {features || "-"}
              </Text>
              <Text style={styles.draftMeta}>
                {t("ai.category", {
                  category: categoryLabel(draft.category_code),
                })}
              </Text>
              <Text style={styles.draftMeta}>
                {t("ai.location", { location: draft.location_text ?? "-" })}
              </Text>
              <Text style={styles.draftMeta}>
                {t("ai.time", {
                  time: draft.event_start_at
                    ? new Date(draft.event_start_at).toLocaleString(
                        locale === "en" ? "en-US" : "ko-KR",
                      )
                    : "-",
                })}
              </Text>
              {draft.warnings.map((warning) => (
                <Text key={warning} style={styles.warning}>
                  {t("ai.reviewWarning", { warning })}
                </Text>
              ))}
              <View style={styles.actions}>
                <Pressable
                  accessibilityRole="button"
                  onPress={edit}
                  disabled={publishing || Boolean(savedPostId)}
                  style={styles.secondaryButton}
                >
                  <Text style={styles.secondaryText}>{t("ai.edit")}</Text>
                </Pressable>
                <Pressable
                  accessibilityRole="button"
                  onPress={() => void publish()}
                  disabled={publishing}
                  style={styles.primaryButton}
                >
                  <Text style={styles.primaryText}>
                    {publishing
                      ? t("ai.publishing")
                      : savedPostId
                        ? t("createPost.retryUpload")
                        : t("ai.publishNow")}
                  </Text>
                </Pressable>
              </View>
            </View>
          ) : null}
          {error ? (
            <Text accessibilityRole="alert" style={styles.error}>
              {error}
            </Text>
          ) : null}
        </ScrollView>
        {photos.length > 0 ? (
          <View style={styles.photoAttachments}>
            <Text style={styles.photoCount}>
              {t("createPost.photoLimit", { count: photos.length })}
            </Text>
            <ScrollView horizontal contentContainerStyle={styles.photos}>
              {photos.map((photo, index) => (
                <View key={`${photo.uri}-${index}`}>
                  <Image source={{ uri: photo.uri }} style={styles.photo} />
                  {!savedPostId ? (
                    <Pressable
                      accessibilityRole="button"
                      accessibilityLabel={t("createPost.removePhoto", {
                        index: index + 1,
                      })}
                      disabled={publishing}
                      onPress={() => removePhoto(index)}
                      style={styles.removePhoto}
                    >
                      <Text style={styles.removePhotoText}>×</Text>
                    </Pressable>
                  ) : null}
                </View>
              ))}
            </ScrollView>
          </View>
        ) : null}
        <View style={styles.composer}>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={t("createPost.addPhoto")}
            accessibilityState={{
              disabled: busy || publishing || Boolean(savedPostId) || photos.length >= 5,
            }}
            disabled={
              busy || publishing || Boolean(savedPostId) || photos.length >= 5
            }
            onPress={() => {
              Keyboard.dismiss();
              setPhotoSheetOpen(true);
            }}
            style={styles.attach}
          >
            <AttachmentIcon />
          </Pressable>
          <TextInput
            value={message}
            onChangeText={setMessage}
            editable={!busy && !publishing}
            multiline
            placeholder={
              ready ? t("ai.editRequestPlaceholder") : t("ai.answerPlaceholder")
            }
            placeholderTextColor="#AAA"
            style={styles.input}
            accessibilityLabel={t("ai.answerAccessibility")}
          />
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={t("ai.sendAnswer")}
            disabled={busy || publishing || !message.trim()}
            onPress={() => void send()}
            style={[
              styles.send,
              (busy || publishing || !message.trim()) && styles.sendDisabled,
            ]}
          >
            <Text style={styles.sendText}>↑</Text>
          </Pressable>
        </View>
      </KeyboardAvoidingView>
      <Modal
        visible={photoSheetOpen}
        transparent
        animationType="fade"
        onRequestClose={() => setPhotoSheetOpen(false)}
        onDismiss={() => {
          const source = pendingPhotoSource.current;
          pendingPhotoSource.current = null;
          if (source) void pickPhotos(source);
        }}
      >
        <View style={styles.sheetOverlay}>
          <Pressable
            style={StyleSheet.absoluteFill}
            accessibilityRole="button"
            accessibilityLabel={t("ai.closePhotoMenu")}
            onPress={() => setPhotoSheetOpen(false)}
          />
          <View style={[styles.photoSheet, { paddingBottom: Math.max(insets.bottom, 16) }]} accessibilityViewIsModal>
            <View style={styles.sheetHandle} />
            <Pressable accessibilityRole="button" onPress={() => selectPhotoSource("camera")} style={({ pressed }) => [styles.photoOption, pressed && styles.photoOptionPressed]}>
              <AttachmentIcon camera />
              <Text style={styles.photoOptionText}>{t("ai.takePhoto")}</Text>
            </Pressable>
            <Pressable accessibilityRole="button" onPress={() => selectPhotoSource("library")} style={({ pressed }) => [styles.photoOption, pressed && styles.photoOptionPressed]}>
              <AttachmentIcon />
              <Text style={styles.photoOptionText}>{t("ai.attachImage")}</Text>
            </Pressable>
          </View>
        </View>
      </Modal>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "white" },
  header: {
    height: 64,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 18,
  },
  back: { width: 44, height: 44, justifyContent: "center" },
  backText: { fontSize: 34, color: "#111" },
  headerTitle: {
    color: "#111",
    fontFamily: Fonts.pretendardSemiBold,
    fontSize: 15,
    textAlign: "center",
  },
  headerSubtitle: {
    color: "#999",
    fontFamily: Fonts.pretendardRegular,
    fontSize: 11,
    marginTop: 2,
    textAlign: "center",
  },
  content: { gap: 14, padding: 22, paddingBottom: 32 },
  messageGroup: { gap: 10 },
  assistantBubble: {
    alignSelf: "flex-start",
    backgroundColor: "#F1F3F2",
    borderRadius: 16,
    maxWidth: "86%",
    padding: 14,
  },
  assistantText: {
    color: "#333",
    fontFamily: Fonts.pretendardRegular,
    fontSize: 14,
    lineHeight: 21,
  },
  userBubble: {
    alignSelf: "flex-end",
    backgroundColor: Colors.primary,
    borderRadius: 16,
    maxWidth: "86%",
    padding: 14,
  },
  userText: {
    color: "white",
    fontFamily: Fonts.pretendardRegular,
    fontSize: 14,
    lineHeight: 21,
  },
  draftCard: {
    backgroundColor: "#F4F7F6",
    borderRadius: 18,
    gap: 10,
    padding: 18,
  },
  previewLabel: {
    color: Colors.primary,
    fontFamily: Fonts.pretendardSemiBold,
    fontSize: 12,
  },
  draftTitle: {
    color: "#111",
    fontFamily: Fonts.pretendardSemiBold,
    fontSize: 17,
  },
  draftText: {
    color: "#444",
    fontFamily: Fonts.pretendardRegular,
    fontSize: 14,
    lineHeight: 21,
  },
  draftMeta: {
    color: "#666",
    fontFamily: Fonts.pretendardRegular,
    fontSize: 13,
  },
  warning: {
    color: "#8A641F",
    fontFamily: Fonts.pretendardRegular,
    fontSize: 12,
  },
  actions: { flexDirection: "row", gap: 10, marginTop: 8 },
  secondaryButton: {
    alignItems: "center",
    borderColor: Colors.primary,
    borderRadius: 12,
    borderWidth: 1,
    flex: 1,
    padding: 13,
  },
  secondaryText: {
    color: Colors.primary,
    fontFamily: Fonts.pretendardSemiBold,
  },
  primaryButton: {
    alignItems: "center",
    backgroundColor: Colors.primary,
    borderRadius: 12,
    flex: 1,
    padding: 13,
  },
  primaryText: { color: "white", fontFamily: Fonts.pretendardSemiBold },
  error: {
    color: "#B54747",
    fontFamily: Fonts.pretendardRegular,
    fontSize: 13,
  },
  composer: {
    alignItems: "flex-end",
    borderTopColor: "#EEE",
    borderTopWidth: 1,
    flexDirection: "row",
    gap: 10,
    padding: 14,
  },
  attach: {
    alignItems: "center",
    borderColor: "#DDD",
    borderRadius: 22,
    borderWidth: 1,
    height: 44,
    justifyContent: "center",
    width: 44,
  },
  sheetOverlay: { flex: 1, justifyContent: "flex-end", backgroundColor: "rgba(0,0,0,0.35)" },
  photoSheet: { backgroundColor: "white", borderTopLeftRadius: 24, borderTopRightRadius: 24, paddingHorizontal: 20, paddingTop: 10 },
  sheetHandle: { width: 36, height: 4, borderRadius: 2, backgroundColor: "#DDD", alignSelf: "center", marginBottom: 12 },
  photoOption: { flexDirection: "row", alignItems: "center", gap: 14, paddingHorizontal: 12, minHeight: 58, borderRadius: 12 },
  photoOptionPressed: { backgroundColor: "#F1F3F2" },
  photoOptionText: { color: "#222", fontSize: 16, fontFamily: Fonts.pretendardMedium },
  photoAttachments: { borderTopColor: "#EEE", borderTopWidth: 1, gap: 8, padding: 12 },
  photoCount: {
    color: "#777",
    fontFamily: Fonts.pretendardRegular,
    fontSize: 12,
  },
  photos: { gap: 10 },
  photo: { borderRadius: 10, height: 72, width: 72 },
  removePhoto: {
    alignItems: "center",
    backgroundColor: "#444",
    borderRadius: 12,
    height: 22,
    justifyContent: "center",
    position: "absolute",
    right: 2,
    top: 2,
    width: 22,
  },
  removePhotoText: { color: "white", fontSize: 18, lineHeight: 20 },
  input: {
    borderColor: "#DDD",
    borderRadius: 18,
    borderWidth: 1,
    color: "#111",
    flex: 1,
    fontFamily: Fonts.pretendardRegular,
    fontSize: 14,
    maxHeight: 120,
    minHeight: 50,
    paddingHorizontal: 15,
    paddingVertical: 12,
    textAlignVertical: "top",
  },
  send: {
    alignItems: "center",
    backgroundColor: Colors.primary,
    borderRadius: 22,
    height: 44,
    justifyContent: "center",
    width: 44,
  },
  sendDisabled: { opacity: 0.4 },
  sendText: { color: "white", fontSize: 24, lineHeight: 26 },
});
