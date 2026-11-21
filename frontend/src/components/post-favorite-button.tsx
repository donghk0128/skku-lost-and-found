import { useCallback, useRef, useState } from "react";
import { useFocusEffect } from "expo-router";
import {
  ActivityIndicator,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { accountApi } from "@/lib/account-api";
import Svg, { Path } from "react-native-svg";
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
      if (active.current && version === generation.current) {
        setSaved(result.saved);
        setReady(true);
        setError("");
      }
    } catch (e) {
      if (active.current && version === generation.current)
        setError(e instanceof Error ? e.message : t("common.requestFailed"));
    }
  }, [postId, t]);
  useFocusEffect(
    useCallback(() => {
      active.current = true;
      generation.current++;
      setReady(false);
      setBusy(pending.current);
      setError("");
      void reload();
      return () => {
        active.current = false;
        generation.current++;
      };
    }, [reload]),
  );
  const toggle = async () => {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setError("");
    try {
      if (!ready) {
        await reload();
        return;
      }
      await accountApi.setFavorite(postId, !saved);
      if (active.current) setSaved(!saved);
    } catch (e) {
      if (active.current)
        setError(e instanceof Error ? e.message : t("common.requestFailed"));
    } finally {
      pending.current = false;
      setBusy(false);
    }
  };
  return (
    <View style={styles.root}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={t(
          !ready && error
            ? "common.retry"
            : saved
              ? "account.unsave"
              : "account.savePost",
        )}
        accessibilityState={{
          selected: saved,
          disabled: busy || (!ready && !error),
          busy,
        }}
        disabled={busy || (!ready && !error)}
        onPress={() => void toggle()}
        style={styles.button}
      >
        {busy || (!ready && !error) ? (
          <ActivityIndicator size="small" color="#EF4444" />
        ) : (
          <Svg
            width={28}
            height={28}
            viewBox="0 0 24 24"
            fill={saved ? "#EF4444" : "none"}
            stroke="#EF4444"
            strokeWidth={1.8}
            strokeLinecap="round"
            strokeLinejoin="round"
          >
            <Path d="M20.8 4.6a5.5 5.5 0 0 0-7.8 0L12 5.7l-1.1-1.1a5.5 5.5 0 0 0-7.8 7.8L12 21l8.8-8.6a5.5 5.5 0 0 0 0-7.8Z" />
          </Svg>
        )}
      </Pressable>
      {error ? (
        <Text accessibilityRole="alert" style={styles.error}>
          {error}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  root: { flexShrink: 0, width: 52, position: "relative" },
  button: {
    minHeight: 52,
    width: 52,
    alignItems: "center",
    justifyContent: "center",
  },
  error: {
    position: "absolute",
    left: 0,
    bottom: 60,
    width: 240,
    padding: 12,
    borderRadius: 12,
    backgroundColor: "#FFF3F3",
    color: "#B33333",
    fontSize: 12,
    lineHeight: 17,
  },
});
