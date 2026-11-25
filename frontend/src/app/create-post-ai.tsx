import { useEffect, useRef, useState } from "react";
import { useLocalSearchParams, useNavigation, useRouter } from "expo-router";
import { CommonActions, useIsFocused, usePreventRemove, type NavigationAction } from "expo-router/react-navigation";
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
  View,
} from "react-native";
import Svg, { Circle, Path, Rect } from "react-native-svg";
import {
  SafeAreaView,
  useSafeAreaInsets,
} from "react-native-safe-area-context";

import { Colors, Fonts } from "@/constants/theme";
import {
  aiApi,
  type AIDraft,
  type AIRequiredFields,
  type PendingField,
  type LocationOption,
} from "@/lib/ai-api";
import AppModal from "@/components/Modal";
import AiProfileIcon from "@/assets/icons/ai-profile.svg";
import ChatThinkingText from "@/components/ChatThinkingText";
import ChatComposer from "@/components/ChatComposer";
import ChatMessageBubble from "@/components/ChatMessageBubble";
import ChatLocationOptions from "@/components/ChatLocationOptions";
import { parseLocationNumbers } from "@/lib/location-selection";
import ChatLocations from "@/components/ChatLocations";
import { locationEntriesFromText, type LocationEntry } from "@/lib/location-entries";
import { authApi } from "@/lib/auth-api";
import { postsApi, type PostImageAsset } from "@/lib/posts-api";
import type { PickedLocation } from "@/lib/location-picker";
import { joinPostDescription } from "@/lib/post-description";
import { readSession, writeSession } from "@/lib/session-storage";
import { useLocale } from "@/i18n/LocaleProvider";
import ChevronLeftIcon from "@/assets/icons/chevron-left.svg";
import { newVisitId, trackEvent } from "@/lib/event-logging";

function AttachmentIcon({ camera = false }: { camera?: boolean }) {
  return (
    <Svg
      width={24}
      height={24}
      viewBox="0 0 24 24"
      fill="none"
      stroke="#666"
      strokeWidth={1.7}
      strokeLinecap="round"
      strokeLinejoin="round"
    >
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
  photos?: PostImageAsset[];
  locationOptions?: LocationOption[];
  selectedLocationIds?: string[];
};

export default function CreatePostAiScreen() {
  const visitId = useRef(newVisitId());
  const viewed = useRef(false);
  useEffect(() => {
    if (!viewed.current) {
      viewed.current = true;
      trackEvent({ event_type: "screen_view", screen: "create_post", visit_id: visitId.current });
    }
  }, []);
  const { locale, t, categoryLabel } = useLocale();
  const router = useRouter();
  const navigation = useNavigation();
  const isFocused = useIsFocused();
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
  const [requiredFields, setRequiredFields] = useState<AIRequiredFields | null>(
    null,
  );
  const [pendingField, setPendingField] = useState<PendingField>(null);
  const [selectedLocationIds, setSelectedLocationIds] = useState<string[]>([]);
  const [collectedFields, setCollectedFields] = useState<
    Partial<Record<"item_name" | "location" | "event_time", string>>
  >({});
  const [confirmedLocation, setConfirmedLocation] =
    useState<PickedLocation | null>(null);
  const [ready, setReady] = useState(false);
  const [mapSkipped, setMapSkipped] = useState(false);
  const [locationEntries, setLocationEntries] = useState<LocationEntry[]>(() => locationEntriesFromText(""));
  const [busy, setBusy] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [error, setError] = useState("");
  const [photos, setPhotos] = useState<PostImageAsset[]>([]);
  const [pendingPhotos, setPendingPhotos] = useState<PostImageAsset[]>([]);
  const photosDirty = pendingPhotos.length > 0;
  const [analyzingImages, setAnalyzingImages] = useState(false);
  const [savedPostId, setSavedPostId] = useState<string | null>(null);
  const features = draft?.keywords.join(", ") ?? "";
  const [leaveAction, setLeaveAction] = useState<NavigationAction | null>(null);
  const [confirmedLeaveAction, setConfirmedLeaveAction] = useState<NavigationAction | null>(null);
  const [publishedPostId, setPublishedPostId] = useState<string | null>(null);
  usePreventRemove(isFocused && !publishedPostId && !confirmedLeaveAction && (!(ready && draft) || publishing), ({ data }) => {
    // Keep publishing in place until the upload finishes or reports an error.
    if (publishing) return;
    Keyboard.dismiss();
    setLeaveAction(data.action);
  });
  useEffect(() => {
    if (!publishedPostId) return;
    // Disable the leave guard first, then keep Home underneath the published post.
    navigation.dispatch(CommonActions.reset({
      index: 1,
      routes: [
        { name: "(tabs)", params: { screen: "index", params: { board: postType, refresh: String(Date.now()) } } },
        { name: "post/[id]", params: { id: publishedPostId } },
      ],
    }));
  }, [publishedPostId, postType, navigation]);
  useEffect(() => {
    if (confirmedLeaveAction) navigation.dispatch(confirmedLeaveAction);
  }, [confirmedLeaveAction, navigation]);
  const back = () => {
    if (publishing) return;
    if (ready && draft) {
      if (router.canGoBack()) router.back();
      else router.replace("/");
      return;
    }
    Keyboard.dismiss();
    // Open the dialog directly, even when a web entry has no previous route.
    setLeaveAction(navigation.canGoBack()
      ? CommonActions.goBack()
      : CommonActions.reset({ index: 0, routes: [{ name: "(tabs)" }] }));
  };
  const confirmLeave = () => {
    if (!leaveAction || publishing) return;
    // Remove the guard before dispatching the approved action.
    setConfirmedLeaveAction(leaveAction);
    setLeaveAction(null);
  };

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
    attachedPhotos: PostImageAsset[] = [],
    selectionAnswer?: { ids?: string[]; correction?: string },
    skipMap = mapSkipped,
  ) => {
    setBusy(true);
    setAnalyzingImages(attachedPhotos.length > 0);
    setError("");
    try {
      const result = await aiApi.continueChat(
        {
          // 현재 화면 언어를 전달해 챗봇의 질문과 초안 언어를 일치시킨다.
          locale,
          post_type: postType,
          // Image-only messages stay text-free in the UI, but the API requires content.
          messages: userMessages.map((item) => ({
            ...item,
            content: item.content.trim() || t("ai.attachImage"),
          })),
          draft: draft ?? undefined,
          required_fields: requiredFields ?? undefined,
          pending_field: pendingField,
          collected_fields: collectedFields,
          selected_location_ids: selectionAnswer?.correction ? [] : selectionAnswer?.ids ?? selectedLocationIds,
          location_correction: selectionAnswer?.correction,
          confirmed_location: location
            ? {
                text: location.address,
                latitude: location.latitude,
                longitude: location.longitude,
              }
            : undefined,
        },
        await authenticatedToken(),
        attachedPhotos,
      );
      setDraft(result.draft);
      setRequiredFields(result.required_fields);
      setPendingField(result.pending_field);
      setSelectedLocationIds(result.selected_location_ids);
      setCollectedFields(result.collected_fields);
      setReady(
        result.status === "READY" && Boolean(result.draft) && (Boolean(location) || skipMap),
      );
      const hasAllRequiredInputs = (
        ["item_name", "location", "event_time"] as const
      ).every(
        (field) =>
          !result.required_fields.missing_fields.includes(field) ||
          Boolean(result.collected_fields[field]),
      );
      const shouldShowLocationPicker =
        !locationPickerShown.current && !location && !skipMap && hasAllRequiredInputs && result.pending_field !== "location_selection";
      if (shouldShowLocationPicker) {
        locationPickerShown.current = true;
        setLocationEntries(locationEntriesFromText(result.required_fields.location_text ?? result.draft?.location_text ?? ""));
      }
      setMessages((current) => [
        ...current,
        {
          role: "assistant",
          content: result.pending_field === "location_selection"
            ? t("ai.chooseLocationsPrompt")
            : result.assistant_message + (result.pending_field === "location" ? `\n\n${t("ai.multipleLocationsHint")}` : ""),
          locationOptions: result.pending_field === "location_selection" ? result.required_fields.location_options : undefined,
          selectedLocationIds: result.selected_location_ids,
          showLocationPicker: shouldShowLocationPicker,
        },
      ]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t("ai.responseFailed"));
    } finally {
      setBusy(false);
      setAnalyzingImages(false);
    }
  };

  const selectLocationOptions = async (ids: string[]) => {
    if (busy || publishing || pendingField !== "location_selection") return;
    const options = requiredFields?.location_options ?? [];
    const selected = options.filter(option => ids.includes(option.id));
    if (!selected.length) return;
    const nextMessages: ChatMessage[] = [...messages, { role: "user", content: selected.map(option => option.label).join(", ") }];
    setMessages(nextMessages);
    setMessage("");
    setReady(false);
    setConfirmedLocation(null);
    locationPickerShown.current = false;
    setSelectedLocationIds(selected.map(option => option.id));
    setMapSkipped(false);
    const userMessages = nextMessages.filter(item => item.role === "user").slice(-12).map(item => ({ role: "user" as const, content: item.content }));
    await continueChat(userMessages, null, [], { ids: selected.map(option => option.id) }, false);
  };

  const send = async () => {
    const content = message.trim();
    const attachedPhotos = pendingPhotos;
    if ((!content && !photosDirty) || busy || publishing) return;
    let selectionAnswer: { ids?: string[]; correction?: string } | undefined;
    if (pendingField === "location_selection" && content) {
      const parsed = parseLocationNumbers(content, requiredFields?.location_options ?? []);
      if (parsed.kind === "selection") {
        await selectLocationOptions(parsed.ids);
        return;
      }
      if (parsed.kind === "invalid") {
        setError(t("ai.invalidLocationNumbers"));
        return;
      }
      if (content.length > 255) {
        setError(t("ai.locationCorrectionTooLong"));
        return;
      }
      selectionAnswer = { correction: content };
      setMapSkipped(false);
      setSelectedLocationIds([]);
      setConfirmedLocation(null);
      locationPickerShown.current = false;
    } else if (pendingField === "location") {
      selectionAnswer = { ids: [] };
      setMapSkipped(false);
      setSelectedLocationIds([]);
    }
    const location =
      selectionAnswer?.correction || (pendingField === "location" && confirmedLocation?.address !== content)
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
        photos: photosDirty ? [...attachedPhotos] : undefined,
      },
    ];
    const userMessages = nextMessages
      .filter(
        (item): item is { role: "user"; content: string } =>
          item.role === "user",
      )
      .map(({ role, content }) => ({ role, content }))
      .slice(-12);
    setMessages(nextMessages);
    setMessage("");
    setPendingPhotos([]);
    setReady(false);
    await continueChat(userMessages, location, attachedPhotos, selectionAnswer, selectionAnswer ? false : mapSkipped);
  };

  const updateLocations = (entries: LocationEntry[]) => {
    setMapSkipped(false);
    setLocationEntries(entries);
    setConfirmedLocation(null);
    setReady(false);
  };
  const confirmLocations = async (entries: LocationEntry[]) => {
    if (busy || publishing || !entries.length || entries.some(row => !row.pin)) return;
    const primary = entries[0];
    if (!primary.pin) return;
    setMapSkipped(false);
    const location = { ...primary.pin, address: primary.text.trim() || primary.pin.address };
    setConfirmedLocation(location);
    setReady(false);
    locationPickerShown.current = true;
    const userMessages = messages.filter(item => item.role === "user").slice(-12).map(item => ({ role: "user" as const, content: item.content }));
    await continueChat(userMessages, location, [], undefined, false);
  };
  const skipLocationsMap = async () => {
    if (busy || publishing || ready) return;
    const first = locationEntries[0];
    const location = first?.pin ? { ...first.pin, address: first.text.trim() || first.pin.address } : null;
    setMapSkipped(true);
    setConfirmedLocation(location);
    locationPickerShown.current = true;
    if (draft) {
      setMessages((current) => [
        ...current,
        { role: "assistant", content: t("ai.reviewDraftPrompt") },
      ]);
      setReady(true);
      return;
    }
    const userMessages = messages.filter(item => item.role === "user").slice(-12).map(item => ({ role: "user" as const, content: item.content }));
    await continueChat(userMessages, location, [], undefined, true);
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
      const result =
        source === "camera"
          ? await ImagePicker.launchCameraAsync({
              mediaTypes: ["images"],
              quality: 0.8,
            })
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
      setPendingPhotos((current) => [...current, ...result.assets].slice(0, 5));
      setError("");
    } catch {
      setError(
        t(
          source === "camera"
            ? "ai.cameraFailed"
            : "createPost.photoPermission",
        ),
      );
    }
  };

  const selectPhotoSource = (source: "camera" | "library") => {
    setPhotoSheetOpen(false);
    // iOS must dismiss the sheet before presenting the system camera/picker.
    if (Platform.OS === "ios") pendingPhotoSource.current = source;
    else void pickPhotos(source);
  };

  const removePhoto = (index: number) => {
    if (savedPostId || publishing || busy) return;
    const removed = pendingPhotos[index];
    setPendingPhotos((current) => current.filter((_, currentIndex) => currentIndex !== index));
    setPhotos((current) => current.filter((photo) => photo !== removed));
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
            location_text: confirmedLocation?.address ?? draft.location_text ?? undefined,
            ...(confirmedLocation
              ? {
                  latitude: confirmedLocation.latitude,
                  longitude: confirmedLocation.longitude,
                }
              : !mapSkipped && draft.latitude !== null && draft.longitude !== null
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
      const uploadedImages = savedPostId ? await postsApi.images(postId) : [];
      for (let index = uploadedImages.length; index < photos.length; index++) {
        setError(
          t("createPost.uploadingPhoto", {
            current: index + 1,
            total: photos.length,
          }),
        );
        await postsApi.upload(postId, photos[index], token);
      }
      setPublishedPostId(postId);
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
        place: confirmedLocation?.address ?? draft.location_text ?? "",
        locationEntries: JSON.stringify(locationEntries),
        latitude: String(confirmedLocation?.latitude ?? (mapSkipped ? "" : draft.latitude ?? "")),
        longitude: String(
          confirmedLocation?.longitude ?? (mapSkipped ? "" : draft.longitude ?? ""),
        ),
        startAt: draft.event_start_at ?? "",
        endAt: draft.event_end_at ?? "",
        photoAssets: JSON.stringify(
          photos.map(({ uri, fileName }) => ({ uri, fileName })),
        ),
      },
    });
  };

  const activeLocationOptionsIndex = messages.reduce((last, item, index) => item.locationOptions?.length ? index : last, -1);

  return (
    <SafeAreaView style={styles.root}>
      <KeyboardAvoidingView
        style={styles.root}
        behavior={Platform.OS === "ios" ? "padding" : "height"}
      >
        <View style={styles.header}>
          <Pressable
            accessibilityRole="button"
            accessibilityLabel={t("common.back")}
            disabled={publishing}
            accessibilityState={{ disabled: publishing }}
            onPress={back}
            style={styles.back}
          >
            <ChevronLeftIcon width={24} height={24} color={"#000000"} />
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
                <ChatLocations
                  disabled={busy || publishing || Boolean(savedPostId)}
                  locations={locationEntries}
                  onChange={updateLocations}
                  onConfirm={entries => { void confirmLocations(entries); }}
                  onSkip={() => { void skipLocationsMap(); }}
                  confirmed={Boolean(confirmedLocation)}
                />
              ) : (
                <>
                  {item.photos?.length ? <View style={[styles.sentPhotos, { alignSelf: "flex-end" }]}>
                    {item.photos.map((photo, photoIndex) => <Image key={`${photo.uri}-${photoIndex}`} source={{ uri: photo.uri }} accessibilityLabel={t("board.photoAccessibility")} style={item.photos?.length === 1 ? styles.sentPhoto : styles.sentPhotoTile} />)}
                  </View> : null}
                  {item.content ? <ChatMessageBubble message={item} own={item.role === "user"} locale={locale} showTime={false} showAvatar={item.role === "assistant"} avatar={<AiProfileIcon width={28} height={28} />} compact /> : null}
                </>
              )}
              {item.locationOptions?.length ? <ChatLocationOptions
                options={item.locationOptions}
                initialSelectedIds={item.selectedLocationIds}
                disabled={busy || publishing || Boolean(savedPostId) || pendingField !== "location_selection" || index !== activeLocationOptionsIndex}
                onConfirm={ids => { void selectLocationOptions(ids); }}
              /> : null}
            </View>
          ))}
          {busy ? (
            <ChatThinkingText text={t(analyzingImages ? "ai.analyzingImages" : "ai.organizingAnswer")} />
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
        <View style={styles.composerContainer}>
        {pendingPhotos.length > 0 ? (
          <View style={styles.photoAttachments}>
            <Text style={styles.photoCount}>
              {t("createPost.photoLimit", { count: pendingPhotos.length })}
            </Text>
            <ScrollView horizontal contentContainerStyle={styles.photos}>
              {pendingPhotos.map((photo, index) => (
                <View key={`${photo.uri}-${index}`}>
                  <Image source={{ uri: photo.uri }} style={styles.photo} />
                  {!savedPostId ? (
                    <Pressable
                      accessibilityRole="button"
                      accessibilityLabel={t("createPost.removePhoto", {
                        index: index + 1,
                      })}
                      disabled={publishing || busy}
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
        <ChatComposer
          value={message}
          onChangeText={setMessage}
          onAttach={() => { Keyboard.dismiss(); setPhotoSheetOpen(true); }}
          onSend={() => { void send(); }}
          inputDisabled={busy || publishing}
          attachmentDisabled={busy || publishing || Boolean(savedPostId) || photos.length >= 5}
          sendDisabled={busy || publishing || (!message.trim() && !photosDirty)}
          busy={busy || publishing}
          placeholder={ready ? t("ai.editRequestPlaceholder") : t("ai.answerPlaceholder")}
          inputAccessibilityLabel={t("ai.answerAccessibility")}
          attachAccessibilityLabel={t("createPost.addPhoto")}
          sendAccessibilityLabel={t("ai.sendAnswer")}
          attachmentIcon={<AttachmentIcon />}
        />
        </View>
      </KeyboardAvoidingView>
      <AppModal
        visible={leaveAction !== null}
        title={t("ai.leaveTitle")}
        description={t(savedPostId ? "ai.leaveSavedDescription" : "ai.leaveDescription")}
        confirmLabel={t("ai.leaveConfirm")}
        onConfirm={confirmLeave}
        onClose={() => setLeaveAction(null)}
        icon={
          <Svg width={24} height={24} viewBox="0 0 24 24" fill="none" stroke={Colors.primary} strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round">
            <Path d="M20 11.5a8 8 0 0 1-8 8H5l-3 2v-10a9 9 0 1 1 18 0Z" />
            <Path d="M7 10h7M7 14h4" />
          </Svg>
        }
      />
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
          <View
            style={[
              styles.photoSheet,
              { paddingBottom: Math.max(insets.bottom, 16) },
            ]}
            accessibilityViewIsModal
          >
            <View style={styles.sheetHandle} />
            <Pressable
              accessibilityRole="button"
              onPress={() => selectPhotoSource("camera")}
              style={({ pressed }) => [
                styles.photoOption,
                pressed && styles.photoOptionPressed,
              ]}
            >
              <AttachmentIcon camera />
              <Text style={styles.photoOptionText}>{t("ai.takePhoto")}</Text>
            </Pressable>
            <Pressable
              accessibilityRole="button"
              onPress={() => selectPhotoSource("library")}
              style={({ pressed }) => [
                styles.photoOption,
                pressed && styles.photoOptionPressed,
              ]}
            >
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
  root: { flex: 1, backgroundColor: Colors.background },
  header: { height: 64, flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: 18 },
  back: { width: 44, height: 44, justifyContent: "center" },
  headerTitle: { color: "#111", fontFamily: Fonts.pretendardSemiBold, fontSize: 15, textAlign: "center" },
  headerSubtitle: { color: "#999", fontFamily: Fonts.pretendardRegular, fontSize: 11, marginTop: 2, textAlign: "center" },
  content: { flexGrow: 1, justifyContent: "flex-start", paddingHorizontal: 24, paddingVertical: 20, gap: 16, width: "100%", maxWidth: 760, alignSelf: "center" },
  messageGroup: { gap: 10 },
  sentPhotos: { width: 220, maxWidth: "100%", flexDirection: "row", flexWrap: "wrap", gap: 6 },
  sentPhoto: { width: 220, maxWidth: "100%", height: 220, borderRadius: 8 },
  sentPhotoTile: { width: 100, height: 100, borderRadius: 8 },
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
  composerContainer: { borderTopWidth: 1, borderTopColor: "#E7ECE9" },
  sheetOverlay: {
    flex: 1,
    justifyContent: "flex-end",
    backgroundColor: "rgba(0,0,0,0.35)",
  },
  photoSheet: {
    backgroundColor: "white",
    borderTopLeftRadius: 24,
    borderTopRightRadius: 24,
    paddingHorizontal: 20,
    paddingTop: 10,
  },
  sheetHandle: {
    width: 36,
    height: 4,
    borderRadius: 2,
    backgroundColor: "#DDD",
    alignSelf: "center",
    marginBottom: 12,
  },
  photoOption: {
    flexDirection: "row",
    alignItems: "center",
    gap: 14,
    paddingHorizontal: 12,
    minHeight: 58,
    borderRadius: 12,
  },
  photoOptionPressed: { backgroundColor: "#F1F3F2" },
  photoOptionText: {
    color: "#222",
    fontSize: 16,
    fontFamily: Fonts.pretendardMedium,
  },
  photoAttachments: {
    gap: 10,
    paddingHorizontal: 14,
    paddingTop: 12,
  },
  photoCount: {
    color: "#777",
    fontFamily: Fonts.pretendardRegular,
    fontSize: 12,
  },
  photos: { gap: 10 },
  photo: { borderRadius: 12, height: 88, width: 88 },
  removePhoto: {
    alignItems: "center",
    backgroundColor: "#17392E",
    borderRadius: 14,
    height: 28,
    justifyContent: "center",
    position: "absolute",
    right: 2,
    top: 2,
    width: 28,
  },
  removePhotoText: { color: "white", fontSize: 22, lineHeight: 24 },
});
