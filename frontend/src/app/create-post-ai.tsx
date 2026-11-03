import { useRef, useState } from "react";
import { useLocalSearchParams, useRouter } from "expo-router";
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { Colors, Fonts } from "@/constants/theme";
import { aiApi, type AIDraft } from "@/lib/ai-api";
import { authApi } from "@/lib/auth-api";
import { postsApi } from "@/lib/posts-api";
import { joinPostDescription } from "@/lib/post-description";
import { readSession, writeSession } from "@/lib/session-storage";
import { useLocale } from "@/i18n/LocaleProvider";

type ChatMessage = { role: "user" | "assistant"; content: string };

export default function CreatePostAiScreen() {
  const { locale, t, categoryLabel } = useLocale();
  const router = useRouter();
  const scrollRef = useRef<ScrollView>(null);
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
  const [pendingField, setPendingField] = useState<"item_name" | "location" | "event_time" | null>(null);
  const [collectedFields, setCollectedFields] = useState<Partial<Record<"item_name" | "location" | "event_time", string>>>({});
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [publishing, setPublishing] = useState(false);
  const [error, setError] = useState("");
  const features = draft?.keywords.join(", ") ?? "";

  const authenticatedToken = async () => {
    const session = await readSession();
    if (!session) throw new Error(t("common.loginRequired"));
    const refreshed = await authApi.refresh(session.refresh_token);
    session.access_token = refreshed.access_token;
    await writeSession(session);
    return session.access_token;
  };

  const send = async () => {
    const content = message.trim();
    if (!content || busy || publishing) return;
    const nextMessages = [...messages, { role: "user" as const, content }];
    const userMessages = nextMessages.filter((item): item is { role: "user"; content: string } => item.role === "user").slice(-12);
    setMessages(nextMessages);
    setMessage("");
    setBusy(true);
    setReady(false);
    setError("");
    try {
      const result = await aiApi.continueChat({
        // 현재 화면 언어를 전달해 챗봇의 질문과 초안 언어를 일치시킨다.
        locale,
        post_type: postType,
        messages: userMessages,
        draft: draft ?? undefined,
        pending_field: pendingField,
        collected_fields: collectedFields,
      }, await authenticatedToken());
      setDraft(result.draft);
      setPendingField(result.pending_field);
      setCollectedFields(result.collected_fields);
      setReady(result.status === "READY");
      setMessages((current) => [...current, { role: "assistant", content: result.assistant_message }]);
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t("ai.responseFailed"));
    } finally {
      setBusy(false);
    }
  };

  const publish = async () => {
    if (!draft || !ready || publishing) return;
    setPublishing(true);
    setError("");
    try {
      const post = await postsApi.createAiAssisted({
        post_type: draft.post_type,
        title: draft.title,
        // 일반 작성과 같은 형식으로 AI 특징을 본문에 합쳐 저장한다.
        description: joinPostDescription(draft.description, features),
        item_name: draft.item_name ?? undefined,
        category_id: draft.category_id,
        location_text: draft.location_text ?? undefined,
        event_start_at: draft.event_start_at ?? undefined,
        event_end_at: draft.event_end_at ?? undefined,
      }, await authenticatedToken());
      router.dismissAll();
      router.replace({ pathname: "/post/[id]", params: { id: post.id } });
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : t("ai.publishFailed"));
      setPublishing(false);
    }
  };

  const edit = () => {
    if (!draft) return;
    router.push({ pathname: "/create-post", params: {
      type: draft.post_type,
      creationMethod: "AI_ASSISTED",
      title: draft.title,
      description: draft.description,
      features,
      categoryId: String(draft.category_id),
      place: draft.location_text ?? "",
      startAt: draft.event_start_at ?? "",
      endAt: draft.event_end_at ?? "",
    } });
  };

  return (
    <SafeAreaView style={styles.root}>
      <KeyboardAvoidingView style={styles.root} behavior={Platform.OS === "ios" ? "padding" : "height"}>
        <View style={styles.header}>
          <Pressable accessibilityLabel={t("common.back")} onPress={() => router.back()} style={styles.back}><Text style={styles.backText}>‹</Text></Pressable>
          <View><Text style={styles.headerTitle}>{t("ai.title")}</Text><Text style={styles.headerSubtitle}>{t("ai.subtitle")}</Text></View>
          <View style={styles.back} />
        </View>
        <ScrollView ref={scrollRef} contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled" onContentSizeChange={() => scrollRef.current?.scrollToEnd({ animated: true })}>
          {messages.map((item, index) => (
            <View key={`${item.role}-${index}`} style={item.role === "user" ? styles.userBubble : styles.assistantBubble}>
              <Text style={item.role === "user" ? styles.userText : styles.assistantText}>{item.content}</Text>
            </View>
          ))}
          {busy ? <View style={styles.assistantBubble}><Text style={styles.assistantText}>{t("ai.organizingAnswer")}</Text></View> : null}
          {ready && draft ? (
            <View style={styles.draftCard}>
              <Text style={styles.previewLabel}>{t("ai.preview")}</Text>
              <Text style={styles.draftTitle}>{draft.title}</Text>
              <Text style={styles.draftText}>{draft.description}</Text>
              <Text style={styles.draftMeta}>{t("createPost.features")}: {features || "-"}</Text>
              <Text style={styles.draftMeta}>{t("ai.category", { category: categoryLabel(draft.category_code) })}</Text>
              <Text style={styles.draftMeta}>{t("ai.location", { location: draft.location_text ?? "-" })}</Text>
              <Text style={styles.draftMeta}>{t("ai.time", { time: draft.event_start_at ? new Date(draft.event_start_at).toLocaleString(locale === "en" ? "en-US" : "ko-KR") : "-" })}</Text>
              {draft.warnings.map((warning) => <Text key={warning} style={styles.warning}>{t("ai.reviewWarning", { warning })}</Text>)}
              <View style={styles.actions}>
                <Pressable accessibilityRole="button" onPress={edit} disabled={publishing} style={styles.secondaryButton}><Text style={styles.secondaryText}>{t("ai.edit")}</Text></Pressable>
                <Pressable accessibilityRole="button" onPress={() => void publish()} disabled={publishing} style={styles.primaryButton}><Text style={styles.primaryText}>{publishing ? t("ai.publishing") : t("ai.publishNow")}</Text></Pressable>
              </View>
            </View>
          ) : null}
          {error ? <Text accessibilityRole="alert" style={styles.error}>{error}</Text> : null}
        </ScrollView>
        <View style={styles.composer}>
          <TextInput value={message} onChangeText={setMessage} editable={!busy && !publishing} multiline placeholder={ready ? t("ai.editRequestPlaceholder") : t("ai.answerPlaceholder")} placeholderTextColor="#AAA" style={styles.input} accessibilityLabel={t("ai.answerAccessibility")} />
          <Pressable accessibilityRole="button" accessibilityLabel={t("ai.sendAnswer")} disabled={busy || publishing || !message.trim()} onPress={() => void send()} style={[styles.send, (busy || publishing || !message.trim()) && styles.sendDisabled]}><Text style={styles.sendText}>↑</Text></Pressable>
        </View>
      </KeyboardAvoidingView>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "white" },
  header: { height: 64, flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: 18 },
  back: { width: 44, height: 44, justifyContent: "center" },
  backText: { fontSize: 34, color: "#111" },
  headerTitle: { color: "#111", fontFamily: Fonts.pretendardSemiBold, fontSize: 15, textAlign: "center" },
  headerSubtitle: { color: "#999", fontFamily: Fonts.pretendardRegular, fontSize: 11, marginTop: 2, textAlign: "center" },
  content: { gap: 14, padding: 22, paddingBottom: 32 },
  assistantBubble: { alignSelf: "flex-start", backgroundColor: "#F1F3F2", borderRadius: 16, maxWidth: "86%", padding: 14 },
  assistantText: { color: "#333", fontFamily: Fonts.pretendardRegular, fontSize: 14, lineHeight: 21 },
  userBubble: { alignSelf: "flex-end", backgroundColor: Colors.primary, borderRadius: 16, maxWidth: "86%", padding: 14 },
  userText: { color: "white", fontFamily: Fonts.pretendardRegular, fontSize: 14, lineHeight: 21 },
  draftCard: { backgroundColor: "#F4F7F6", borderRadius: 18, gap: 10, padding: 18 },
  previewLabel: { color: Colors.primary, fontFamily: Fonts.pretendardSemiBold, fontSize: 12 },
  draftTitle: { color: "#111", fontFamily: Fonts.pretendardSemiBold, fontSize: 17 },
  draftText: { color: "#444", fontFamily: Fonts.pretendardRegular, fontSize: 14, lineHeight: 21 },
  draftMeta: { color: "#666", fontFamily: Fonts.pretendardRegular, fontSize: 13 },
  warning: { color: "#8A641F", fontFamily: Fonts.pretendardRegular, fontSize: 12 },
  actions: { flexDirection: "row", gap: 10, marginTop: 8 },
  secondaryButton: { alignItems: "center", borderColor: Colors.primary, borderRadius: 12, borderWidth: 1, flex: 1, padding: 13 },
  secondaryText: { color: Colors.primary, fontFamily: Fonts.pretendardSemiBold },
  primaryButton: { alignItems: "center", backgroundColor: Colors.primary, borderRadius: 12, flex: 1, padding: 13 },
  primaryText: { color: "white", fontFamily: Fonts.pretendardSemiBold },
  error: { color: "#B54747", fontFamily: Fonts.pretendardRegular, fontSize: 13 },
  composer: { alignItems: "flex-end", borderTopColor: "#EEE", borderTopWidth: 1, flexDirection: "row", gap: 10, padding: 14 },
  input: { borderColor: "#DDD", borderRadius: 18, borderWidth: 1, color: "#111", flex: 1, fontFamily: Fonts.pretendardRegular, fontSize: 14, maxHeight: 120, minHeight: 50, paddingHorizontal: 15, paddingVertical: 12, textAlignVertical: "top" },
  send: { alignItems: "center", backgroundColor: Colors.primary, borderRadius: 22, height: 44, justifyContent: "center", width: 44 },
  sendDisabled: { opacity: 0.4 },
  sendText: { color: "white", fontSize: 24, lineHeight: 26 },
});
