import { useCallback, useRef, useState } from "react";
import { useFocusEffect } from "expo-router";
import { ActivityIndicator, Pressable, StyleSheet, Text, View } from "react-native";
import { accountApi } from "@/lib/account-api";
import { Colors, Fonts } from "@/constants/theme";
import { useLocale } from "@/i18n/LocaleProvider";

export default function PostFavoriteButton({ postId }: { postId: string }) {
  const { t } = useLocale();
  const [saved, setSaved] = useState(false);
  const [ready, setReady] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const pending = useRef(false);
  const active = useRef(false);
  const generation = useRef(0);
  const reload = useCallback(async () => {
    const version = generation.current;
    try {
      const result = await accountApi.favoriteState(postId);
      if (active.current && version === generation.current) { setSaved(result.saved); setReady(true); setError(""); }
    } catch (e) {
      if (active.current && version === generation.current) setError(e instanceof Error ? e.message : t("common.requestFailed"));
    }
  }, [postId, t]);
  useFocusEffect(useCallback(() => {
    active.current = true;
    generation.current++;
    setReady(false);
    setBusy(pending.current);
    setError("");
    void reload();
    return () => { active.current = false; generation.current++; };
  }, [reload]));
  const toggle = async () => {
    if (pending.current) return;
    pending.current = true; setBusy(true); setError("");
    try {
      if (!ready) { await reload(); return; }
      await accountApi.setFavorite(postId, !saved);
      if (active.current) setSaved(!saved);
    } catch (e) {
      if (active.current) setError(e instanceof Error ? e.message : t("common.requestFailed"));
    } finally {
      pending.current = false;
      setBusy(false);
    }
  };
  return <View style={styles.root}>
    <Pressable accessibilityRole="button" accessibilityLabel={t(!ready && error ? "common.retry" : saved ? "account.unsave" : "account.savePost")}
      accessibilityState={{ selected: saved, disabled: busy || (!ready && !error), busy }}
      disabled={busy || (!ready && !error)} onPress={() => void toggle()} style={styles.button}>
      {!ready && !error ? <ActivityIndicator size="small" color={Colors.primary} /> : <Text style={styles.label}>
        {!ready ? t("common.retry") : `${saved ? "♥" : "♡"} ${t(saved ? "account.unsave" : "account.savePost")}`}
      </Text>}
    </Pressable>
    {error ? <Text accessibilityRole="alert" style={styles.error}>{error}</Text> : null}
  </View>;
}

const styles = StyleSheet.create({
  root: { flexShrink: 0, maxWidth: "46%", alignItems: "flex-end" },
  button: { minHeight: 44, justifyContent: "center", paddingVertical: 10, paddingLeft: 8 },
  label: { color: Colors.primary, fontSize: 14, fontFamily: Fonts.pretendardMedium, textAlign: "right" },
  error: { color: "#B33333", fontSize: 12, lineHeight: 17, textAlign: "right" },
});
