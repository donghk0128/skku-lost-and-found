import { useRef, useState } from "react";
import { useRouter } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import { Fonts } from "@/constants/theme";
import { useAuth } from "@/providers/AuthProvider";

export default function SettingsScreen() {
  const router = useRouter();
  const { signOut } = useAuth();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const pending = useRef(false);
  const logout = async () => {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setError("");
    try {
      await signOut();
      // Protected routes remove authenticated screens when user becomes null.
    } catch (error) {
      setError(
        error instanceof Error ? error.message : "로그아웃하지 못했습니다.",
      );
    } finally {
      pending.current = false;
      setBusy(false);
    }
  };
  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.content}>
        <View style={styles.header}>
          <Pressable
            disabled={busy}
            accessibilityRole="button"
            accessibilityLabel="뒤로가기"
            onPress={() =>
              router.canGoBack() ? router.back() : router.replace("/")
            }
            style={styles.back}
          >
            <Text style={styles.backText}>‹</Text>
          </Pressable>
          <Text style={styles.title}>설정</Text>
          <View style={styles.back} />
        </View>
        <Pressable
          accessibilityRole="button"
          accessibilityState={{ disabled: busy, busy }}
          disabled={busy}
          onPress={() => void logout()}
          style={styles.logout}
        >
          <Text style={styles.label}>{busy ? "로그아웃 중…" : "로그아웃"}</Text>
          <Text style={styles.chevron}>›</Text>
        </Pressable>
        {error ? (
          <Text accessibilityRole="alert" style={styles.error}>
            ⓘ {error}
          </Text>
        ) : null}
      </View>
    </SafeAreaView>
  );
}
const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "white" },
  content: {
    width: "100%",
    maxWidth: 640,
    alignSelf: "center",
    paddingHorizontal: 24,
  },
  header: {
    height: 64,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    marginBottom: 24,
  },
  back: { width: 44, height: 44, justifyContent: "center" },
  backText: { fontSize: 34, color: "#222" },
  title: { fontSize: 18, fontFamily: Fonts.pretendardSemiBold, color: "#222" },
  logout: {
    minHeight: 60,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    borderBottomWidth: 1,
    borderColor: "#EEE",
  },
  label: { fontSize: 16, color: "#333", fontFamily: Fonts.pretendardMedium },
  chevron: { fontSize: 24, color: "#999" },
  error: {
    marginTop: 16,
    fontSize: 13,
    lineHeight: 20,
    color: "#B54747",
    fontFamily: Fonts.pretendardRegular,
  },
});
