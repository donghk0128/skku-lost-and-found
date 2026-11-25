import { useCallback, useEffect, useRef, useState } from "react";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import * as ImagePicker from "expo-image-picker";
import {
  ActivityIndicator,
  AppState,
  FlatList,
  Image,
  KeyboardAvoidingView,
  Modal,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from "react-native";
import Svg, { Circle, Path } from "react-native-svg";
import type { NativeScrollEvent, NativeSyntheticEvent } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Colors, Fonts } from "@/constants/theme";
import {
  chatApi,
  chatSocketUrl,
  chatToken,
  type ChatMessage,
  type ChatRoom,
  type PairCandidate,
} from "@/lib/chat-api";
import { useAuth } from "@/providers/AuthProvider";
import { useLocale } from "@/i18n/LocaleProvider";
import ChatComposer from "@/components/ChatComposer";
import ChatMessageBubble from "@/components/ChatMessageBubble";
import ChatPostCard from "@/components/ChatPostCard";
import { newVisitId, trackEvent } from "@/lib/event-logging";

const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;

export default function ChatRoute() {
  const { id } = useLocalSearchParams<{ id: string }>();
  return <ChatDetail key={id} id={id} />;
}

function ChatDetail({ id }: { id: string }) {
  const visitId = useRef(newVisitId());
  const viewed = useRef(false);
  const router = useRouter();
  const { user } = useAuth();
  const { t, locale } = useLocale();
  const [room, setRoom] = useState<ChatRoom>();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [text, setText] = useState("");
  const [attachments, setAttachments] = useState<
    ImagePicker.ImagePickerAsset[]
  >([]);
  const [previewUri, setPreviewUri] = useState<string | null>(null);
  const [pickingPhoto, setPickingPhoto] = useState(false);
  const [connected, setConnected] = useState(false);
  const [reload, setReload] = useState({ showLoading: true });
  const [closeReason, setCloseReason] = useState<"RETURNED" | "GENERAL" | null>(
    null,
  );
  const [pairCandidates, setPairCandidates] = useState<PairCandidate[]>([]);
  const [pairCandidatesUnavailable, setPairCandidatesUnavailable] = useState(false);
  const [selectedPair, setSelectedPair] = useState<string | null>(null);
  const [menu, setMenu] = useState(false);
  const menuTrigger = useRef<View>(null);
  const { width: windowWidth, height: windowHeight } = useWindowDimensions();
  const [menuAnchor, setMenuAnchor] = useState({ left: 16, top: 64 });
  const menuWidth = Math.min(264, windowWidth - 32);
  const dismissMenu = () => {
    if (pending.current) return;
    setMenu(false);
    setCloseReason(null);
  };
  const showMenu = () => {
    void chatApi.room(id).then(setRoom).catch(() => undefined);
    menuTrigger.current?.measureInWindow((x, y, width, height) => {
      setMenuAnchor({
        left: Math.max(
          16,
          Math.min(x + width - menuWidth, windowWidth - menuWidth - 16),
        ),
        top: Math.max(16, Math.min(y + height + 8, windowHeight - 180)),
      });
      setCloseReason(null);
      setMenu(true);
    });
  };
  const [foreground, setForeground] = useState(
    AppState.currentState === "active",
  );
  const [showLatest, setShowLatest] = useState(false);
  const sequence = useRef(0);
  const messageCache = useRef(new Map<string, ChatMessage>());
  const readSequence = useRef(0);
  const list = useRef<FlatList<ChatMessage>>(null);
  const pending = useRef(false);
  const pickingPhotoRef = useRef(false);
  const sendAttempt = useRef<{ signature: string; id: string } | null>(null);
  const followLatest = useRef(true);
  const lastScrollOffset = useRef(0);
  const focused = useRef(false);
  const merge = useCallback((items: ChatMessage[]) => {
    if (!items.length) return;
    items.forEach((item) => messageCache.current.set(item.id, item));
    const ordered = [...messageCache.current.values()].sort(
      (a, b) => a.sequence - b.sequence,
    );
    const sequences = new Set(ordered.map((item) => item.sequence));
    while (sequences.has(sequence.current + 1)) sequence.current += 1;
    setMessages(ordered);
  }, []);
  useEffect(() => {
    const subscription = AppState.addEventListener("change", (state) =>
      setForeground(state === "active"),
    );
    return () => subscription.remove();
  }, []);
  useFocusEffect(
    useCallback(() => {
      focused.current = true;
      if (!foreground)
        return () => {
          focused.current = false;
        };
      setLoading(reload.showLoading && messageCache.current.size === 0);
      let active = true;
      let socket: WebSocket | undefined;
      let timer: ReturnType<typeof setTimeout> | undefined;
      let retryDelay = 1000;
      const connect = async () => {
        try {
          const detail = await chatApi.room(id);
          if (!active) return;
          setRoom(detail);
          if (!viewed.current) {
            viewed.current = true;
            trackEvent({ event_type: "screen_view", screen: "chat", visit_id: visitId.current });
          }
          readSequence.current = detail.last_read_sequence;
          let hasMore = true;
          while (hasMore && active) {
            const page = await chatApi.messages(id, sequence.current);
            if (!active) return;
            merge(page.items);
            hasMore = page.has_more;
          }
          if (!active) return;
          setLoading(false);
          setError("");
          if (detail.status === "CLOSED") return;
          const token = await chatToken(true);
          if (!active) return;
          socket = new WebSocket(chatSocketUrl(id, sequence.current));
          socket.onopen = () => {
            if (!active) {
              socket?.close();
              return;
            }
            socket?.send(JSON.stringify({ token }));
            setConnected(true);
            retryDelay = 1000;
          };
          socket.onmessage = (event) => {
            if (!active) return;
            try {
              const data = JSON.parse(String(event.data));
              if (data.type === "message") merge([data.message as ChatMessage]);
              else if (data.type === "return_pair") {
                setRoom(current => current ? { ...current, return_pair: data.pair } : current);
              }
              else if (data.type === "room_closed") {
                setRoom((current) =>
                  current
                    ? {
                        ...current,
                        status: "CLOSED",
                        close_reason: data.reason,
                      }
                    : current,
                );
                void chatApi
                  .room(id)
                  .then((detail) => {
                    if (active) setRoom(detail);
                  })
                  .catch((error) => {
                    if (active)
                      setError(
                        error instanceof Error
                          ? error.message
                          : t("common.requestFailed"),
                      );
                  });
              } else if (data.type === "error") setError(data.error.message);
            } catch {
              setError(t("common.requestFailed"));
            }
          };
          socket.onclose = (event) => {
            if (!active) return;
            setConnected(false);
            if (event.code !== 1000 && event.code !== 4404) {
              timer = setTimeout(() => {
                void connect();
              }, retryDelay);
              retryDelay = Math.min(retryDelay * 2, 15000);
            }
          };
          socket.onerror = () => {
            if (active) setConnected(false);
          };
        } catch (e) {
          if (active) {
            setLoading(false);
            setError(
              e instanceof Error ? e.message : t("common.requestFailed"),
            );
            timer = setTimeout(() => {
              void connect();
            }, retryDelay);
            retryDelay = Math.min(retryDelay * 2, 15000);
          }
        }
      };
      void connect();
      return () => {
        active = false;
        focused.current = false;
        setConnected(false);
        if (timer) clearTimeout(timer);
        socket?.close();
      };
    }, [id, reload, foreground, merge, t]),
  );

  const latest = messages.reduce(
    (last, item) => (item.sequence === last + 1 ? item.sequence : last),
    0,
  );
  useEffect(() => {
    if (
      loading ||
      showLatest ||
      !foreground ||
      !focused.current ||
      latest <= readSequence.current
    )
      return;
    const timer = setTimeout(() => {
      void chatApi
        .read(id, latest)
        .then((result) => {
          readSequence.current = Math.max(
            readSequence.current,
            result.last_read_sequence,
          );
        })
        .catch((e) =>
          setError(e instanceof Error ? e.message : t("common.requestFailed")),
        );
    }, 300);
    return () => clearTimeout(timer);
  }, [id, latest, foreground, loading, showLatest, t]);

  const onMessageScroll = (event: NativeSyntheticEvent<NativeScrollEvent>) => {
    const { contentOffset, contentSize, layoutMeasurement } = event.nativeEvent;
    const nearBottom =
      contentSize.height - layoutMeasurement.height - contentOffset.y <= 80;
    const movedUp = contentOffset.y < lastScrollOffset.current - 1;
    lastScrollOffset.current = contentOffset.y;
    // FlatList can grow its render window during the initial scroll to end.
    // Only an upward scroll pauses following; growing content does not.
    if (nearBottom) {
      followLatest.current = true;
      setShowLatest(false);
    } else if (movedUp) {
      followLatest.current = false;
      setShowLatest(true);
    }
  };
  const onMessageLayout = () => {
    if (followLatest.current)
      requestAnimationFrame(() => {
        if (followLatest.current)
          list.current?.scrollToEnd({ animated: false });
      });
  };

  const act = async (action: () => Promise<void>) => {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setError("");
    try {
      await action();
    } catch (e) {
      setError(e instanceof Error ? e.message : t("common.requestFailed"));
    } finally {
      pending.current = false;
      setBusy(false);
    }
  };
  const send = () =>
    act(async () => {
      const value = text.trim();
      if (!value && !attachments.length) return;
      const signature = JSON.stringify([
        attachments.map((asset) => asset.uri),
        value,
      ]);
      if (sendAttempt.current?.signature !== signature) {
        // Correlation key only; not an authentication or security token.
        sendAttempt.current = {
          signature,
          id: `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}`,
        };
      }
      if (attachments.length) {
        const sent = await chatApi.images(
          id,
          attachments,
          value,
          sendAttempt.current.id,
        );
        followLatest.current = true;
        setShowLatest(false);
        merge([sent]);
        setAttachments([]);
        setPreviewUri(null);
        setText("");
      } else if (value) {
        const sent = await chatApi.send(id, value, sendAttempt.current.id);
        followLatest.current = true;
        setShowLatest(false);
        merge([sent]);
        setText("");
      }
      sendAttempt.current = null;
      onMessageLayout();
    });
  const photo = async () => {
    if (pending.current || (Platform.OS !== "web" && pickingPhotoRef.current))
      return;
    // Web picker cancellation is not reliably reported; do not leave the
    // composer locked while awaiting a selection that may never resolve.
    pickingPhotoRef.current = Platform.OS !== "web";
    setPickingPhoto(Platform.OS !== "web");
    setError("");
    try {
      const result = await ImagePicker.launchImageLibraryAsync({
        mediaTypes: ["images"],
        allowsMultipleSelection: true,
        selectionLimit: 0,
        orderedSelection: true,
        quality: 0.8,
      });
      if (result.canceled || !result.assets[0]) return;
      for (const asset of result.assets) {
        if (asset.fileSize && asset.fileSize > 5 * 1024 * 1024)
          throw new Error(t("createPost.photoTooLarge"));
        if (
          asset.mimeType &&
          !["image/jpeg", "image/png", "image/webp"].includes(asset.mimeType)
        )
          throw new Error(t("createPost.unsupportedPhoto"));
      }
      const combined = [
        ...attachments,
        ...result.assets.filter(
          (asset) => !attachments.some((item) => item.uri === asset.uri),
        ),
      ];
      if (
        combined.reduce((total, asset) => total + (asset.fileSize ?? 0), 0) >
        MAX_UPLOAD_BYTES
      )
        throw new Error(t("chat.photosTooLarge"));
      setAttachments(combined);
    } catch (e) {
      setError(
        e instanceof Error ? e.message : t("createPost.photoPermission"),
      );
    } finally {
      pickingPhotoRef.current = false;
      setPickingPhoto(false);
    }
  };
  const closed = room?.status === "CLOSED";
  const composerDisabled = busy || pickingPhoto || loading || !room || closed;
  const sendDisabled =
    composerDisabled || (!text.trim() && !attachments.length);
  return (
    <SafeAreaView style={styles.root}>
      <KeyboardAvoidingView
        style={styles.root}
        behavior={Platform.OS === "ios" ? "padding" : undefined}
      >
        <View style={styles.headerCard}>
          <View style={styles.header}>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={t("common.back")}
              onPress={() =>
                router.canGoBack()
                  ? router.back()
                  : router.replace("/(tabs)/chat")
              }
            >
              <Text style={styles.back}>‹</Text>
            </Pressable>
            <View style={styles.headerAvatar} />
            <View style={styles.heading}>
              <Text style={styles.name}>
                {room?.other_withdrawn
                  ? t("chat.withdrawnUser")
                  : (room?.other_nickname ?? t("tabs.chat"))}
              </Text>
              {closed || !connected ? (
                <Text style={styles.small}>
                  {closed ? t("chat.closed") : t("chat.connecting")}
                </Text>
              ) : null}
            </View>
            <Pressable
              ref={menuTrigger}
              accessibilityRole="button"
              accessibilityLabel={t("chat.menu")}
              accessibilityState={{ expanded: menu }}
              onPress={showMenu}
              style={styles.menuTrigger}
            >
              <Svg width={22} height={22} viewBox="0 0 24 24" fill="#171A19">
                <Circle cx={12} cy={5} r={1.7} />
                <Circle cx={12} cy={12} r={1.7} />
                <Circle cx={12} cy={19} r={1.7} />
              </Svg>
            </Pressable>
          </View>
          {room ? (
            <ChatPostCard
              key={room.post_id}
              postId={room.post_id}
              title={room.post_title}
              deleted={room.post_deleted}
            />
          ) : null}
        </View>
        {error ? (
          <Pressable onPress={() => setReload({ showLoading: true })}>
            <Text accessibilityRole="alert" style={styles.error}>
              {error} · {t("common.retry")}
            </Text>
          </Pressable>
        ) : null}
        {loading ? (
          <ActivityIndicator style={styles.loader} color={Colors.primary} />
        ) : (
          <FlatList
            ref={list}
            data={messages}
            keyExtractor={(item) => item.id}
            contentContainerStyle={styles.messages}
            onContentSizeChange={onMessageLayout}
            onLayout={onMessageLayout}
            onScroll={onMessageScroll}
            scrollEventThrottle={16}
            ListEmptyComponent={
              <Text style={styles.empty}>{t("chat.start")}</Text>
            }
            renderItem={({ item, index }) => {
              const date = new Date(item.created_at);
              const previousDate =
                index > 0 ? new Date(messages[index - 1].created_at) : null;
              const showDate =
                !previousDate ||
                date.toDateString() !== previousDate.toDateString();
              return (
                <View>
                  {showDate ? (
                    <Text style={styles.date}>
                      {date.toLocaleDateString(
                        locale === "en" ? "en-US" : "ko-KR",
                        { year: "numeric", month: "2-digit", day: "2-digit" },
                      )}
                    </Text>
                  ) : null}
                  <ChatMessageBubble
                    message={item}
                    own={item.sender_id === user?.id}
                    locale={locale}
                  />
                </View>
              );
            }}
          />
        )}
        {showLatest ? (
          <Pressable
            accessibilityRole="button"
            style={styles.latestButton}
            onPress={() => {
              followLatest.current = true;
              setShowLatest(false);
              list.current?.scrollToEnd({ animated: true });
            }}
          >
            <Text style={styles.postText}>{t("chat.latestMessages")} ↓</Text>
          </Pressable>
        ) : null}
        {closed ? (
          <View style={styles.closed}>
            <Text style={styles.small}>
              {t(
                room.close_reason === "RETURNED"
                  ? "chat.returned"
                  : room.close_reason === "POST_COMPLETED"
                    ? "chat.postCompleted"
                    : "chat.generalClosed",
              )}
            </Text>
          </View>
        ) : (
          <View style={styles.composerContainer}>
            {room?.return_pair?.status === "PENDING" ? (
              <View style={styles.closed}>
                <Text style={styles.small}>
                  {locale === "ko" ? "반환 게시글 연결 확인 대기 중" : "Waiting for return pair confirmation"}
                </Text>
                <Text style={styles.postText}>
                  {room.post_title} ↔ {room.return_pair.counterpart_post_title}
                </Text>
                {room.return_pair.proposed_by_id !== user?.id ? (
                  <Pressable disabled={busy} onPress={() => void act(async () => setRoom(await chatApi.confirmPair(id)))}>
                    <Text style={styles.postText}>{locale === "ko" ? "게시글 쌍 확인하고 반환 완료" : "Confirm post pair and return"}</Text>
                  </Pressable>
                ) : null}
                <Pressable disabled={busy} onPress={() => void act(async () => setRoom(await chatApi.rejectPair(id)))}>
                  <Text style={styles.small}>{locale === "ko" ? "연결 요청 취소 / 거절" : "Cancel or reject pair"}</Text>
                </Pressable>
              </View>
            ) : null}
            {attachments.length ? (
              <View style={styles.attachments}>
                <Text style={styles.small}>
                  {t("chat.attachmentHint", { count: attachments.length })}
                </Text>
                <ScrollView
                  horizontal
                  contentContainerStyle={styles.attachmentRow}
                >
                  {attachments.map((asset) => (
                    <View key={asset.uri} style={styles.attachment}>
                      <Pressable
                        accessibilityRole="button"
                        accessibilityLabel={t("chat.previewPhoto")}
                        disabled={busy}
                        onPress={() => setPreviewUri(asset.uri)}
                      >
                        <Image
                          source={{ uri: asset.uri }}
                          style={styles.thumbnail}
                        />
                      </Pressable>
                      <Pressable
                        accessibilityRole="button"
                        accessibilityLabel={t("chat.removePhoto")}
                        disabled={busy}
                        onPress={() => {
                          setAttachments((current) =>
                            current.filter((item) => item.uri !== asset.uri),
                          );
                          setPreviewUri(null);
                        }}
                        style={styles.removePhoto}
                      >
                        <Text style={styles.removePhotoText}>×</Text>
                      </Pressable>
                    </View>
                  ))}
                </ScrollView>
              </View>
            ) : null}
            <ChatComposer
              value={text}
              onChangeText={setText}
              onAttach={() => {
                void photo();
              }}
              onSend={() => {
                void send();
              }}
              inputDisabled={Boolean(composerDisabled)}
              sendDisabled={Boolean(sendDisabled)}
              busy={busy}
              maxLength={2000}
            />
          </View>
        )}
        <Modal
          visible={!!previewUri && !closed}
          transparent
          animationType="fade"
          onRequestClose={() => setPreviewUri(null)}
        >
          <View style={styles.photoOverlay}>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={t("common.close")}
              onPress={() => setPreviewUri(null)}
              style={styles.previewClose}
            >
              <Text style={styles.ownText}>{t("common.close")}</Text>
            </Pressable>
            {previewUri ? (
              <Image
                accessibilityLabel={t("chat.previewPhoto")}
                source={{ uri: previewUri }}
                resizeMode="contain"
                style={styles.largePreview}
              />
            ) : null}
          </View>
        </Modal>
        <Modal
          visible={menu}
          transparent
          animationType="fade"
          statusBarTranslucent
          onRequestClose={dismissMenu}
        >
          <View style={closeReason ? styles.overlay : styles.popoverLayer}>
            <Pressable
              style={StyleSheet.absoluteFill}
              accessibilityRole="button"
              accessibilityLabel={t("common.close")}
              disabled={busy}
              onPress={dismissMenu}
            />
            {closeReason ? (
              <View style={styles.sheet} accessibilityViewIsModal>
                <Text style={styles.name}>{t("chat.confirmTitle")}</Text>
                <Text style={styles.confirm}>
                  {t(
                    closeReason === "RETURNED"
                      ? "chat.confirmReturn"
                      : "chat.confirmGeneral",
                  )}
                </Text>
                {closeReason === "RETURNED" && pairCandidates.length > 0 ? (
                  <ScrollView style={{ maxHeight: 190 }}>
                    <Text style={styles.small}>{locale === "ko" ? "연결할 상대방 게시글이 있나요?" : "Is there a matching post?"}</Text>
                    <Pressable style={styles.action} onPress={() => setSelectedPair(null)}>
                      <Text style={styles.small}>{selectedPair === null ? "✓ " : ""}{locale === "ko" ? "없음: 반환만 완료" : "None: complete return only"}</Text>
                    </Pressable>
                    {pairCandidates.map(candidate => (
                      <Pressable key={candidate.id} style={styles.action} onPress={() => setSelectedPair(candidate.id)}>
                        <Text style={styles.small}>{selectedPair === candidate.id ? "✓ " : ""}{candidate.title}</Text>
                      </Pressable>
                    ))}
                  </ScrollView>
                ) : null}
                {closeReason === "RETURNED" && pairCandidatesUnavailable ? (
                  <Text style={styles.small}>
                    {locale === "ko" ? "상대 게시글 조회에 실패했습니다. 다시 열어 재시도하거나 반환만 완료할 수 있습니다." : "Could not load matching posts. Reopen to retry or complete the return only."}
                  </Text>
                ) : null}
                <Pressable
                  accessibilityRole="button"
                  disabled={busy}
                  style={styles.action}
                  onPress={() => {
                    void act(async () => {
                      setRoom(closeReason === "RETURNED" && selectedPair
                        ? await chatApi.proposePair(id, selectedPair)
                        : await chatApi.close(id, closeReason));
                      setMenu(false);
                      setCloseReason(null);
                    });
                  }}
                >
                  <Text style={styles.danger}>{selectedPair
                    ? (locale === "ko" ? "상대방에게 게시글 쌍 확인 요청" : "Request pair confirmation")
                    : t("chat.confirmClose")}</Text>
                </Pressable>
                {error ? (
                  <Text accessibilityRole="alert" style={styles.error}>
                    {error}
                  </Text>
                ) : null}
                <Pressable
                  accessibilityRole="button"
                  disabled={busy}
                  style={styles.action}
                  onPress={dismissMenu}
                >
                  <Text style={styles.small}>{t("common.cancel")}</Text>
                </Pressable>
              </View>
            ) : (
              <View
                style={[styles.popover, menuAnchor, { width: menuWidth }]}
                accessibilityViewIsModal
              >
                {closed ? (
                  <Pressable
                    accessibilityRole="button"
                    disabled={busy}
                    style={({ pressed }) => [
                      styles.popoverItem,
                      pressed && styles.popoverPressed,
                      busy && styles.disabled,
                    ]}
                    onPress={() => {
                      void act(async () => {
                        setRoom(await chatApi.hide(id, !room.is_hidden));
                        setMenu(false);
                        router.replace("/(tabs)/chat");
                      });
                    }}
                  >
                    <Svg
                      width={20}
                      height={20}
                      viewBox="0 0 24 24"
                      fill="none"
                      stroke="#58616A"
                      strokeWidth={1.5}
                      strokeLinecap="round"
                      strokeLinejoin="round"
                    >
                      <Path d="M3 12s3-7 9-7 9 7 9 7-3 7-9 7-9-7-9-7Z" />
                      <Circle cx={12} cy={12} r={3} />
                      {!room.is_hidden ? <Path d="m3 3 18 18" /> : null}
                    </Svg>
                    <Text style={styles.popoverText}>
                      {t(room.is_hidden ? "chat.restore" : "chat.hide")}
                    </Text>
                  </Pressable>
                ) : (
                  <>
                    <Pressable
                      accessibilityRole="button"
                      disabled={busy || !room || loading}
                      style={({ pressed }) => [
                        styles.popoverItem,
                        pressed && styles.popoverPressed,
                        (busy || !room || loading) && styles.disabled,
                      ]}
                      onPress={() => {
                        void act(async () => {
                          setPairCandidatesUnavailable(false);
                          setPairCandidates(await chatApi.pairCandidates(id).catch(() => {
                            setPairCandidatesUnavailable(true);
                            return [];
                          }));
                          setSelectedPair(null);
                          setCloseReason("RETURNED");
                        });
                      }}
                    >
                      <Svg
                        width={20}
                        height={20}
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="#58616A"
                        strokeWidth={1.5}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <Circle cx={12} cy={12} r={9} />
                        <Path d="m8 12 3 3 5-6" />
                      </Svg>
                      <Text style={styles.popoverText}>
                        {t("chat.returnAction")}
                      </Text>
                    </Pressable>
                    <Pressable
                      accessibilityRole="button"
                      disabled={busy || !room || loading}
                      style={({ pressed }) => [
                        styles.popoverItem,
                        pressed && styles.popoverPressed,
                        (busy || !room || loading) && styles.disabled,
                      ]}
                      onPress={() => setCloseReason("GENERAL")}
                    >
                      <Svg
                        width={20}
                        height={20}
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="#58616A"
                        strokeWidth={1.5}
                        strokeLinecap="round"
                        strokeLinejoin="round"
                      >
                        <Path d="M20 11.5a8 8 0 0 1-8 8H5l-3 2v-10a9 9 0 1 1 18 0Z" />
                        <Path d="m9 8 6 6m0-6-6 6" />
                      </Svg>
                      <Text style={styles.popoverText}>
                        {t("chat.generalAction")}
                      </Text>
                    </Pressable>
                  </>
                )}
                {error ? (
                  <Text accessibilityRole="alert" style={styles.error}>
                    {error}
                  </Text>
                ) : null}
              </View>
            )}
          </View>
        </Modal>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  menuTrigger: {
    width: 44,
    height: 44,
    alignItems: "center",
    justifyContent: "center",
  },
  popoverLayer: { flex: 1 },
  popover: {
    position: "absolute",
    paddingVertical: 5,
    borderRadius: 16,
    borderWidth: 1,
    borderColor: "#E1E4E8",
    backgroundColor: "white",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 3 },
    shadowOpacity: 0.08,
    shadowRadius: 10,
    elevation: 5,
  },
  popoverItem: {
    minHeight: 56,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingHorizontal: 18,
    paddingVertical: 12,
    borderRadius: 12,
    marginHorizontal: 4,
  },
  popoverPressed: { backgroundColor: "#F3F5F4" },
  popoverText: {
    flexShrink: 1,
    color: "#222",
    fontSize: 15,
    lineHeight: 22,
    fontFamily: Fonts.pretendardMedium,
  },
  root: { flex: 1, backgroundColor: Colors.background },
  headerCard: {
    backgroundColor: "#F8F8F8",
    borderBottomLeftRadius: 48,
    borderBottomRightRadius: 48,
    paddingBottom: 2,
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 6 },
    shadowOpacity: 0.05,
    shadowRadius: 10,
    elevation: 3,
    zIndex: 1,
  },
  header: {
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
    paddingHorizontal: 24,
    paddingTop: 16,
    paddingBottom: 12,
    minHeight: 72,
  },
  back: { color: "#171A19", fontSize: 30, minWidth: 32, textAlign: "center" },
  headerAvatar: {
    width: 22,
    height: 22,
    borderRadius: 11,
    backgroundColor: "#D9D9D9",
  },
  heading: { flex: 1, gap: 4 },
  name: {
    fontFamily: Fonts.pretendardSemiBold,
    color: "#171A19",
    fontSize: 18,
  },
  small: { color: "#6D7973", fontSize: 12 },
  postText: { color: Colors.primary, fontSize: 14 },
  loader: { flex: 1 },
  messages: {
    flexGrow: 1,
    justifyContent: "flex-end",
    paddingHorizontal: 16,
    paddingVertical: 24,
    gap: 20,
    width: "100%",
    maxWidth: 760,
    alignSelf: "center",
  },
  date: {
    fontFamily: Fonts.pretendardRegular,
    color: "#999D9B",
    fontSize: 13,
    textAlign: "center",
    marginBottom: 32,
    marginTop: 12,
  },
  ownText: { color: "white", fontSize: 14 },
  empty: { textAlign: "center", color: "#6D7973", padding: 40 },
  latestButton: {
    alignSelf: "center",
    paddingHorizontal: 18,
    paddingVertical: 10,
    margin: 8,
    borderRadius: 20,
    backgroundColor: Colors.softgreen,
  },
  composerContainer: { borderTopWidth: 1, borderTopColor: "#E7ECE9" },
  attachments: { paddingHorizontal: 14, paddingTop: 12, gap: 10 },
  attachmentRow: { flexDirection: "row", gap: 12, paddingRight: 8 },
  attachment: { position: "relative", paddingTop: 6, paddingRight: 6 },
  thumbnail: {
    width: 88,
    height: 88,
    borderRadius: 12,
    backgroundColor: "#EEF3EF",
  },
  removePhoto: {
    position: "absolute",
    top: 0,
    right: 0,
    width: 28,
    height: 28,
    borderRadius: 14,
    backgroundColor: "#17392E",
    justifyContent: "center",
    alignItems: "center",
  },
  removePhotoText: { color: "white", fontSize: 22, lineHeight: 24 },
  photoOverlay: {
    flex: 1,
    padding: 24,
    backgroundColor: "#000000EB",
    justifyContent: "center",
  },
  previewClose: { alignSelf: "flex-end", padding: 14 },
  largePreview: { flex: 1, width: "100%" },
  disabled: { opacity: 0.4 },
  closed: { padding: 20, backgroundColor: "#EEF3EF", alignItems: "center" },
  error: { color: "#B54747", padding: 14 },
  overlay: {
    flex: 1,
    backgroundColor: "#00000066",
    justifyContent: "center",
    padding: 24,
  },
  sheet: {
    width: "100%",
    maxWidth: 440,
    alignSelf: "center",
    borderRadius: 24,
    padding: 24,
    backgroundColor: "white",
    gap: 16,
  },
  action: { paddingVertical: 14 },
  confirm: { fontSize: 15, lineHeight: 24, color: "#47594F" },
  danger: { color: "#B54747", fontSize: 15 },
});
