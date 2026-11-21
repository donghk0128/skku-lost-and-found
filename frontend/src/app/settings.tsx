import { useRef, useState } from "react";
import { useRouter } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import AppModal from "@/components/Modal";
import { Fonts } from "@/constants/theme";
import ChevronLeftIcon from "@/assets/icons/chevron-left.svg";
import { useAuth } from "@/providers/AuthProvider";
import { useLocale } from "@/i18n/LocaleProvider";

export default function SettingsScreen() {
  const { t } = useLocale();
  const router = useRouter();
  const { signOut } = useAuth();
  const [busy, setBusy] = useState(false);
  const [confirmLogout, setConfirmLogout] = useState(false);
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
        error instanceof Error ? error.message : t("settings.logoutFailed"),
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
            accessibilityLabel={t("common.back")}
            onPress={() =>
              router.canGoBack() ? router.back() : router.replace("/")
            }
            style={styles.back}
          >
            <ChevronLeftIcon width={24} height={24} color={"#000000"} />
          </Pressable>
          <Text style={styles.title}>{t("settings.title")}</Text>
          <View style={styles.back} />
        </View>
        <Pressable
          accessibilityRole="button"
          accessibilityState={{ disabled: busy, busy }}
          disabled={busy}
          onPress={() => setConfirmLogout(true)}
          style={styles.logout}
        >
          <Text style={styles.label}>
            {busy ? t("settings.loggingOut") : t("settings.logout")}
          </Text>
          <Text style={styles.chevron}>›</Text>
        </Pressable>

      </View>
      <AppModal
        visible={confirmLogout}
        title={t("account.logoutConfirm")}
        description={t("account.logoutDescription")}
        confirmLabel={busy ? t("settings.loggingOut") : t("settings.logout")}
        loading={busy}
        errorMessage={error}
        onConfirm={() => void logout()}
        onClose={() => { setConfirmLogout(false); setError(""); }}
      />
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
