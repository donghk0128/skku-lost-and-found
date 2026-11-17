import { useCallback, useEffect, useRef, useState } from "react";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import * as ImagePicker from "expo-image-picker";
import { ActivityIndicator, AppState, FlatList, Image, KeyboardAvoidingView, Modal, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import type { NativeScrollEvent, NativeSyntheticEvent } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Colors, Fonts } from "@/constants/theme";
import { chatApi, chatSocketUrl, chatToken, type ChatMessage, type ChatRoom } from "@/lib/chat-api";
import { useAuth } from "@/providers/AuthProvider";
import { useLocale } from "@/i18n/LocaleProvider";
import ChatImageGallery from "@/components/ChatImageGallery";

const MAX_UPLOAD_BYTES = 50 * 1024 * 1024;

export default function ChatRoute() {
  const { id } = useLocalSearchParams<{ id: string }>();
  return <ChatDetail key={id} id={id} />;
}

function ChatDetail({ id }: { id: string }) {
  const router = useRouter();
  const { user } = useAuth();
  const { t, locale } = useLocale();
  const [room, setRoom] = useState<ChatRoom>();
  const [messages, setMessages] = useState<ChatMessage[]>([]);
  const [error, setError] = useState("");
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [text, setText] = useState("");
  const [attachments, setAttachments] = useState<ImagePicker.ImagePickerAsset[]>([]);
  const [previewUri, setPreviewUri] = useState<string | null>(null);
  const [pickingPhoto, setPickingPhoto] = useState(false);
  const [connected, setConnected] = useState(false);
  const [reload, setReload] = useState({ showLoading: true });
  const [closeReason, setCloseReason] = useState<"RETURNED" | "GENERAL" | null>(null);
  const [menu, setMenu] = useState(false);
  const [foreground, setForeground] = useState(AppState.currentState === "active");
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
    items.forEach(item => messageCache.current.set(item.id, item));
    const ordered = [...messageCache.current.values()].sort((a, b) => a.sequence - b.sequence);
    const sequences = new Set(ordered.map(item => item.sequence));
    while (sequences.has(sequence.current + 1)) sequence.current += 1;
    setMessages(ordered);
  }, []);
  useEffect(() => {
    const subscription = AppState.addEventListener("change", state => setForeground(state === "active"));
    return () => subscription.remove();
  }, []);
  useFocusEffect(useCallback(() => {
    focused.current = true;
    if (!foreground) return () => { focused.current = false; };
    setLoading(reload.showLoading && messageCache.current.size === 0);
    let active = true;
    let socket: WebSocket | undefined;
    let timer: ReturnType<typeof setTimeout> | undefined;
    let retryDelay = 1000;
    const connect = async () => {
      try {
        const detail = await chatApi.room(id);
        if (!active) return;
        setRoom(detail); readSequence.current = detail.last_read_sequence;
        let hasMore = true;
        while (hasMore && active) {
          const page = await chatApi.messages(id, sequence.current);
          if (!active) return;
          merge(page.items); hasMore = page.has_more;
        }
        if (!active) return;
        setLoading(false); setError("");
        if (detail.status === "CLOSED") return;
        const token = await chatToken(true);
        if (!active) return;
        socket = new WebSocket(chatSocketUrl(id, sequence.current));
        socket.onopen = () => {
          if (!active) { socket?.close(); return; }
          socket?.send(JSON.stringify({ token })); setConnected(true); retryDelay = 1000;
        };
        socket.onmessage = event => {
          if (!active) return;
          try {
            const data = JSON.parse(String(event.data));
            if (data.type === "message") merge([data.message as ChatMessage]);
            else if (data.type === "room_closed") {
              setRoom(current => current ? { ...current, status: "CLOSED", close_reason: data.reason } : current);
            } else if (data.type === "error") setError(data.error.message);
          } catch { setError(t("common.requestFailed")); }
        };
        socket.onclose = event => {
          if (!active) return;
          setConnected(false);
          if (event.code !== 1000 && event.code !== 4404) {
            timer = setTimeout(() => { void connect(); }, retryDelay);
            retryDelay = Math.min(retryDelay * 2, 15000);
          }
        };
        socket.onerror = () => { if (active) setConnected(false); };
      } catch (e) {
        if (active) {
          setLoading(false); setError(e instanceof Error ? e.message : t("common.requestFailed"));
          timer = setTimeout(() => { void connect(); }, retryDelay);
          retryDelay = Math.min(retryDelay * 2, 15000);
        }
      }
    };
    void connect();
    return () => { active = false; focused.current = false; setConnected(false); if (timer) clearTimeout(timer); socket?.close(); };
  }, [id, reload, foreground, merge, t]));

  const latest = messages.reduce((last, item) => item.sequence === last + 1 ? item.sequence : last, 0);
  useEffect(() => {
    if (loading || showLatest || !foreground || !focused.current || latest <= readSequence.current) return;
    const timer = setTimeout(() => {
      void chatApi.read(id, latest).then(result => { readSequence.current = Math.max(readSequence.current, result.last_read_sequence); })
        .catch(e => setError(e instanceof Error ? e.message : t("common.requestFailed")));
    }, 300);
    return () => clearTimeout(timer);
  }, [id, latest, foreground, loading, showLatest, t]);

  const onMessageScroll = (event: NativeSyntheticEvent<NativeScrollEvent>) => {
    const { contentOffset, contentSize, layoutMeasurement } = event.nativeEvent;
    const nearBottom = contentSize.height - layoutMeasurement.height - contentOffset.y <= 80;
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
    if (followLatest.current) requestAnimationFrame(() => {
      if (followLatest.current) list.current?.scrollToEnd({ animated: false });
    });
  };

  const act = async (action: () => Promise<void>) => {
    if (pending.current) return;
    pending.current = true; setBusy(true); setError("");
    try { await action(); }
    catch (e) { setError(e instanceof Error ? e.message : t("common.requestFailed")); }
    finally { pending.current = false; setBusy(false); }
  };
  const send = () => act(async () => {
    const value = text.trim();
    if (!value && !attachments.length) return;
    const signature = JSON.stringify([attachments.map(asset => asset.uri), value]);
    if (sendAttempt.current?.signature !== signature) {
      // Correlation key only; not an authentication or security token.
      sendAttempt.current = { signature, id: `${Date.now().toString(36)}-${Math.random().toString(36).slice(2)}-${Math.random().toString(36).slice(2)}` };
    }
    if (attachments.length) {
      const sent = await chatApi.images(id, attachments, value, sendAttempt.current.id);
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
    if (pending.current || (Platform.OS !== "web" && pickingPhotoRef.current)) return;
    // Web picker cancellation is not reliably reported; do not leave the
    // composer locked while awaiting a selection that may never resolve.
    pickingPhotoRef.current = Platform.OS !== "web";
    setPickingPhoto(Platform.OS !== "web");
    setError("");
    try {
      const result = await ImagePicker.launchImageLibraryAsync({ mediaTypes: ["images"], allowsMultipleSelection: true, selectionLimit: 0, orderedSelection: true, quality: 0.8 });
      if (result.canceled || !result.assets[0]) return;
      for (const asset of result.assets) {
        if (asset.fileSize && asset.fileSize > 5 * 1024 * 1024) throw new Error(t("createPost.photoTooLarge"));
        if (asset.mimeType && !["image/jpeg", "image/png", "image/webp"].includes(asset.mimeType)) throw new Error(t("createPost.unsupportedPhoto"));
      }
      const combined = [...attachments, ...result.assets.filter(asset => !attachments.some(item => item.uri === asset.uri))];
      if (combined.reduce((total, asset) => total + (asset.fileSize ?? 0), 0) > MAX_UPLOAD_BYTES) throw new Error(t("chat.photosTooLarge"));
      setAttachments(combined);
    } catch (e) { setError(e instanceof Error ? e.message : t("createPost.photoPermission")); }
    finally { pickingPhotoRef.current = false; setPickingPhoto(false); }
  };
  const closed = room?.status === "CLOSED";
  const composerDisabled = busy || pickingPhoto || loading || !room || closed;
  const sendDisabled = composerDisabled || (!text.trim() && !attachments.length);
  return <SafeAreaView style={styles.root}>
    <KeyboardAvoidingView style={styles.root} behavior={Platform.OS === "ios" ? "padding" : undefined}>
      <View style={styles.header}>
        <Pressable accessibilityRole="button" accessibilityLabel={t("common.back")} onPress={() => router.canGoBack() ? router.back() : router.replace("/(tabs)/chat")}><Text style={styles.back}>‹</Text></Pressable>
        <View style={styles.heading}><Text style={styles.name}>{room?.other_nickname ?? t("tabs.chat")}</Text><Text style={styles.small}>{closed ? t("chat.closed") : connected ? t("chat.connected") : t("chat.connecting")}</Text></View>
        <Pressable accessibilityRole="button" accessibilityLabel={t("chat.menu")} onPress={() => setMenu(true)}><Text style={styles.back}>···</Text></Pressable>
      </View>
      {room ? <Pressable style={styles.post} onPress={() => router.push({ pathname: "/post/[id]", params: { id: room.post_id } })}><Text numberOfLines={1} style={styles.postText}>{room.post_title} ›</Text></Pressable> : null}
      {error ? <Pressable onPress={() => setReload({ showLoading: true })}><Text accessibilityRole="alert" style={styles.error}>{error} · {t("common.retry")}</Text></Pressable> : null}
      {loading ? <ActivityIndicator style={styles.loader} color={Colors.primary} /> : <FlatList ref={list} data={messages} keyExtractor={item => item.id}
        contentContainerStyle={styles.messages} onContentSizeChange={onMessageLayout}
        onLayout={onMessageLayout} onScroll={onMessageScroll} scrollEventThrottle={16}
        ListEmptyComponent={<Text style={styles.empty}>{t("chat.start")}</Text>}
        renderItem={({ item }) => {
          const own = item.sender_id === user?.id;
          return <View style={[styles.message, own && styles.own]}>
            {!own ? <Text style={styles.small}>{room?.other_nickname}</Text> : null}
            <View style={[styles.bubble, own && styles.ownBubble]}>
              {item.images?.length ? <ChatImageGallery images={item.images} /> : null}
              {item.content ? <Text selectable style={[styles.messageText, own && styles.ownText]}>{item.content}</Text> : null}
            </View>
            <Text style={styles.time}>{new Date(item.created_at).toLocaleString(locale === "en" ? "en-US" : "ko-KR", { month: "short", day: "numeric", hour: "2-digit", minute: "2-digit" })}</Text>
          </View>;
        }} />}
      {showLatest ? <Pressable accessibilityRole="button" style={styles.latestButton} onPress={() => { followLatest.current = true; setShowLatest(false); list.current?.scrollToEnd({ animated: true }); }}><Text style={styles.postText}>{t("chat.latestMessages")} ↓</Text></Pressable> : null}
      {closed ? <View style={styles.closed}><Text style={styles.small}>{t(room.close_reason === "RETURNED" ? "chat.returned" : room.close_reason === "POST_COMPLETED" ? "chat.postCompleted" : "chat.generalClosed")}</Text></View>
        : <View style={styles.composerContainer}>
          {attachments.length ? <View style={styles.attachments}>
            <Text style={styles.small}>{t("chat.attachmentHint", { count: attachments.length })}</Text>
            <ScrollView horizontal contentContainerStyle={styles.attachmentRow}>{attachments.map(asset => <View key={asset.uri} style={styles.attachment}>
              <Pressable accessibilityRole="button" accessibilityLabel={t("chat.previewPhoto")} disabled={busy} onPress={() => setPreviewUri(asset.uri)}>
                <Image source={{ uri: asset.uri }} style={styles.thumbnail} />
              </Pressable>
              <Pressable accessibilityRole="button" accessibilityLabel={t("chat.removePhoto")} disabled={busy} onPress={() => { setAttachments(current => current.filter(item => item.uri !== asset.uri)); setPreviewUri(null); }} style={styles.removePhoto}><Text style={styles.removePhotoText}>×</Text></Pressable>
            </View>)}</ScrollView>
          </View> : null}
          <View style={styles.composer}>
            <Pressable accessibilityRole="button" accessibilityLabel={t("chat.attach")} disabled={composerDisabled} onPress={() => { void photo(); }} style={composerDisabled && styles.disabled}><Text style={styles.attach}>＋</Text></Pressable>
            <TextInput accessibilityLabel={t("chat.placeholder")} placeholder={t("chat.placeholder")} value={text} onChangeText={setText} maxLength={2000} multiline editable={!composerDisabled} style={styles.input} />
            <Pressable accessibilityRole="button" accessibilityState={{ disabled: sendDisabled, busy }} disabled={sendDisabled} onPress={() => { void send(); }} style={[styles.send, sendDisabled && styles.disabled]}><Text style={styles.ownText}>{busy ? "…" : t("chat.send")}</Text></Pressable>
          </View>
        </View>}
      <Modal visible={!!previewUri && !closed} transparent animationType="fade" onRequestClose={() => setPreviewUri(null)}>
        <View style={styles.photoOverlay}>
          <Pressable accessibilityRole="button" accessibilityLabel={t("common.close")} onPress={() => setPreviewUri(null)} style={styles.previewClose}><Text style={styles.ownText}>{t("common.close")}</Text></Pressable>
          {previewUri ? <Image accessibilityLabel={t("chat.previewPhoto")} source={{ uri: previewUri }} resizeMode="contain" style={styles.largePreview} /> : null}
        </View>
      </Modal>
      <Modal visible={menu} transparent animationType="fade" onRequestClose={() => { if (!busy) { setMenu(false); setCloseReason(null); } }}>
        <View style={styles.overlay}><View style={styles.sheet}>
          <Text style={styles.name}>{closeReason ? t("chat.confirmTitle") : t("chat.menu")}</Text>
          {closeReason ? <>
            <Text style={styles.confirm}>{t(closeReason === "RETURNED" ? "chat.confirmReturn" : "chat.confirmGeneral")}</Text>
            <Pressable disabled={busy} style={styles.action} onPress={() => { void act(async () => { setRoom(await chatApi.close(id, closeReason)); setMenu(false); setCloseReason(null); }); }}><Text style={styles.danger}>{t("chat.confirmClose")}</Text></Pressable>
          </> : closed ? <Pressable disabled={busy} style={styles.action} onPress={() => { void act(async () => { setRoom(await chatApi.hide(id, !room.is_hidden)); setMenu(false); router.replace("/(tabs)/chat"); }); }}><Text style={styles.postText}>{t(room.is_hidden ? "chat.restore" : "chat.hide")}</Text></Pressable> : <>
            <Pressable disabled={busy} style={styles.action} onPress={() => setCloseReason("RETURNED")}><Text style={styles.postText}>{t("chat.returnAction")}</Text></Pressable>
            <Pressable disabled={busy} style={styles.action} onPress={() => setCloseReason("GENERAL")}><Text style={styles.postText}>{t("chat.generalAction")}</Text></Pressable>
          </>}
          {error ? <Text accessibilityRole="alert" style={styles.error}>{error}</Text> : null}
          <Pressable disabled={busy} style={styles.action} onPress={() => { setMenu(false); setCloseReason(null); }}><Text style={styles.small}>{t("common.cancel")}</Text></Pressable>
        </View></View>
      </Modal>
    </KeyboardAvoidingView>
  </SafeAreaView>;
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: Colors.background },
  header: { flexDirection: "row", alignItems: "center", gap: 20, paddingHorizontal: 20, paddingVertical: 12, borderBottomWidth: 1, borderBottomColor: "#E7ECE9" },
  back: { color: Colors.primary, fontSize: 30, minWidth: 32, textAlign: "center" },
  heading: { flex: 1, gap: 4 }, name: { fontFamily: Fonts.pretendardSemiBold, color: "#17392E", fontSize: 18 },
  small: { color: "#6D7973", fontSize: 12 }, post: { padding: 16, backgroundColor: Colors.softgreen }, postText: { color: Colors.primary, fontSize: 14 },
  loader: { flex: 1 }, messages: { padding: 20, gap: 16, width: "100%", maxWidth: 760, alignSelf: "center" },
  message: { alignItems: "flex-start", gap: 5, maxWidth: "85%" }, own: { alignSelf: "flex-end", alignItems: "flex-end" },
  bubble: { padding: 12, gap: 8, borderRadius: 16, backgroundColor: "#EDF1EE" }, ownBubble: { backgroundColor: Colors.primary },
  messageText: { fontSize: 15, lineHeight: 22, color: "#17392E" }, ownText: { color: "white", fontSize: 14 }, time: { fontSize: 10, color: "#7D8982" },
  empty: { textAlign: "center", color: "#6D7973", padding: 40 },
  latestButton: { alignSelf: "center", paddingHorizontal: 18, paddingVertical: 10, margin: 8, borderRadius: 20, backgroundColor: Colors.softgreen },
  composerContainer: { borderTopWidth: 1, borderTopColor: "#E7ECE9" },
  attachments: { paddingHorizontal: 14, paddingTop: 12, gap: 10 },
  attachmentRow: { flexDirection: "row", gap: 12, paddingRight: 8 },
  attachment: { position: "relative", paddingTop: 6, paddingRight: 6 },
  thumbnail: { width: 88, height: 88, borderRadius: 12, backgroundColor: "#EEF3EF" },
  removePhoto: { position: "absolute", top: 0, right: 0, width: 28, height: 28, borderRadius: 14, backgroundColor: "#17392E", justifyContent: "center", alignItems: "center" },
  removePhotoText: { color: "white", fontSize: 22, lineHeight: 24 },
  photoOverlay: { flex: 1, padding: 24, backgroundColor: "#000000EB", justifyContent: "center" },
  previewClose: { alignSelf: "flex-end", padding: 14 }, largePreview: { flex: 1, width: "100%" },
  composer: { flexDirection: "row", alignItems: "flex-end", gap: 10, padding: 14 },
  attach: { fontSize: 28, color: Colors.primary, paddingVertical: 4 }, input: { flex: 1, maxHeight: 120, minHeight: 44, padding: 12, backgroundColor: "#F0F4F1", borderRadius: 16, fontSize: 15 },
  send: { backgroundColor: Colors.primary, padding: 13, borderRadius: 16 }, disabled: { opacity: 0.4 },
  closed: { padding: 20, backgroundColor: "#EEF3EF", alignItems: "center" }, error: { color: "#B54747", padding: 14 },
  overlay: { flex: 1, backgroundColor: "#00000066", justifyContent: "center", padding: 24 },
  sheet: { width: "100%", maxWidth: 440, alignSelf: "center", borderRadius: 24, padding: 24, backgroundColor: "white", gap: 16 },
  action: { paddingVertical: 14 }, confirm: { fontSize: 15, lineHeight: 24, color: "#47594F" }, danger: { color: "#B54747", fontSize: 15 },
});
