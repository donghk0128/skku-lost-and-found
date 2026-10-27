import { useState } from "react";
import { useLocalSearchParams, useRouter } from "expo-router";
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { aiApi, type AIDraft } from "@/lib/ai-api";
import { authApi } from "@/lib/auth-api";
import { readSession, writeSession } from "@/lib/session-storage";
import { Colors, Fonts } from "@/constants/theme";

export default function CreatePostAiScreen() {
  const router = useRouter();
  const { type } = useLocalSearchParams<{ type?: string }>();
  const postType = type === "FOUND" ? "FOUND" : "LOST";
  const [message, setMessage] = useState("");
  const [sentMessage, setSentMessage] = useState("");
  const [draft, setDraft] = useState<AIDraft | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");

  const generate = async () => {
    const naturalLanguage = message.trim();
    if (!naturalLanguage || busy) return;
    setBusy(true);
    setError("");
    setSentMessage(naturalLanguage);
    try {
      const session = await readSession();
      if (!session) throw new Error("로그인이 필요합니다.");
      const refreshed = await authApi.refresh(session.refresh_token);
      session.access_token = refreshed.access_token;
      await writeSession(session);
      setDraft(await aiApi.createDraft({ post_type: postType, natural_language: naturalLanguage }, session.access_token));
    } catch (cause) {
      setError(cause instanceof Error ? cause.message : "AI 초안을 만들지 못했습니다.");
    } finally {
      setBusy(false);
    }
  };

  return (
    <SafeAreaView style={styles.root}>
      <KeyboardAvoidingView style={styles.root} behavior={Platform.OS === "ios" ? "padding" : "height"}>
        <View style={styles.header}>
          <Pressable accessibilityLabel="뒤로가기" onPress={() => router.back()} style={styles.back}>
            <Text style={styles.backText}>‹</Text>
          </Pressable>
          <View><Text style={styles.headerTitle}>게시글 작성 도우미</Text><Text style={styles.headerSubtitle}>AI 초안</Text></View>
          <View style={styles.back} />
        </View>
        <ScrollView contentContainerStyle={styles.content} keyboardShouldPersistTaps="handled">
          <View style={styles.assistantBubble}><Text style={styles.assistantText}>언제, 어디서, 무엇을 {postType === "LOST" ? "잃어버렸는지" : "주웠는지"} 설명해주세요.</Text></View>
          {sentMessage ? <View style={styles.userBubble}><Text style={styles.userText}>{sentMessage}</Text></View> : null}
          {busy ? <View style={styles.assistantBubble}><Text style={styles.assistantText}>내용을 분석하고 있어요…</Text></View> : null}
          {draft ? <View style={styles.draftCard}><Text style={styles.draftTitle}>{draft.title}</Text><Text style={styles.draftText}>{draft.description}</Text><Text style={styles.draftMeta}>카테고리: {draft.category_code}</Text><Text style={styles.draftMeta}>장소: {draft.location_text ?? "확인이 필요해요"}</Text><Text style={styles.draftMeta}>시간: {draft.event_start_at ?? "확인이 필요해요"}</Text><Text style={styles.draftNotice}>장소·시간 선택과 최종 수정 화면은 다음 단계에서 연결됩니다.</Text></View> : null}
          {error ? <Text accessibilityRole="alert" style={styles.error}>{error}</Text> : null}
        </ScrollView>
        <View style={styles.composer}><TextInput value={message} onChangeText={setMessage} editable={!busy} multiline placeholder="상황을 설명해주세요" placeholderTextColor="#AAA" style={styles.input} accessibilityLabel="AI 게시글 상황 설명" /><Pressable accessibilityRole="button" accessibilityLabel="AI 초안 생성" disabled={busy || !message.trim()} onPress={() => void generate()} style={[styles.send, (busy || !message.trim()) && styles.sendDisabled]}><Text style={styles.sendText}>↑</Text></Pressable></View>
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
  draftTitle: { color: "#111", fontFamily: Fonts.pretendardSemiBold, fontSize: 17 },
  draftText: { color: "#444", fontFamily: Fonts.pretendardRegular, fontSize: 14, lineHeight: 21 },
  draftMeta: { color: "#666", fontFamily: Fonts.pretendardRegular, fontSize: 13 },
  draftNotice: { color: "#888", fontFamily: Fonts.pretendardRegular, fontSize: 12, lineHeight: 18, marginTop: 4 },
  error: { color: "#B54747", fontFamily: Fonts.pretendardRegular, fontSize: 13 },
  composer: { alignItems: "flex-end", borderTopColor: "#EEE", borderTopWidth: 1, flexDirection: "row", gap: 10, padding: 14 },
  input: { borderColor: "#DDD", borderRadius: 18, borderWidth: 1, color: "#111", flex: 1, fontFamily: Fonts.pretendardRegular, fontSize: 14, maxHeight: 120, minHeight: 50, paddingHorizontal: 15, paddingVertical: 12, textAlignVertical: "top" },
  send: { alignItems: "center", backgroundColor: Colors.primary, borderRadius: 22, height: 44, justifyContent: "center", width: 44 },
  sendDisabled: { opacity: 0.4 },
  sendText: { color: "white", fontSize: 24, lineHeight: 26 },
});
