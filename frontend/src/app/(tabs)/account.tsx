import { useRef, useState } from "react";
import { useRouter } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";
import AppModal from "@/components/Modal";
import NotificationPreferenceRow from "@/components/NotificationPreferenceRow";
import { AccountScreen } from "@/components/account-screen";
import { ProfileMenuItem } from "@/components/profile-menu";
import { Colors, Fonts } from "@/constants/theme";
import { useAuth } from "@/providers/AuthProvider";
import { useLocale } from "@/i18n/LocaleProvider";

export default function Account() {
  const { user, signOut } = useAuth();
  const { t } = useLocale();
  const router = useRouter();
  const [confirmLogout, setConfirmLogout] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const pending = useRef(false);
  const logout = async () => {
    if (pending.current) return;
    pending.current = true; setBusy(true); setError("");
    try { await signOut(); }
    catch (e) { setError(e instanceof Error ? e.message : t("common.requestFailed")); }
    finally { pending.current = false; setBusy(false); }
  };
  const nickname = user?.nickname ?? "";
  const initial = Array.from(nickname.trim())[0]?.toUpperCase() ?? "•";

  return <AccountScreen title={t("tabs.account")} tab>
    <View style={styles.profile}>
      <View style={styles.avatar} accessible={false}>
        <Text style={styles.initial} accessible={false}>{initial}</Text>
      </View>
      <View style={styles.identity}>
        <Text style={styles.name}>{nickname}</Text>
        <Text selectable style={styles.email}>{user?.email}</Text>
      </View>
      <Pressable
        accessibilityRole="button"
        onPress={() => router.push("/profile-edit")}
        style={({ pressed }) => [styles.editButton, pressed && styles.pressedEdit]}
      >
        <Text style={styles.editLabel}>{t("account.editProfile")}</Text>
      </Pressable>
    </View>

    <View style={styles.section}>
      <Text accessibilityRole="header" style={styles.heading}>{t("account.activitySection")}</Text>
      <View style={styles.menu}>
        <ProfileMenuItem label={t("account.myPosts")} ios="doc.text" material="article" onPress={() => router.push("/my-posts")} />
        <ProfileMenuItem label={t("account.favorites")} ios="heart" material="favorite" onPress={() => router.push("/favorites")} />
      </View>
    </View>

    <View style={styles.section}>
      <Text accessibilityRole="header" style={styles.heading}>{t("account.settingsSection")}</Text>
      <View style={styles.menu}>
        <NotificationPreferenceRow />
        <ProfileMenuItem label={t("account.keywords")} ios="line.3.horizontal.decrease" material="tune" onPress={() => router.push("/keyword-conditions")} />
        <ProfileMenuItem label={t("account.logout")} ios="rectangle.portrait.and.arrow.right" material="logout" onPress={() => setConfirmLogout(true)} />
        <ProfileMenuItem label={t("account.withdraw")} ios="person.crop.circle.badge.minus" material="person_remove" onPress={() => router.push("/withdrawal")} danger />
      </View>
    </View>
    <AppModal
      visible={confirmLogout}
      title={t("account.logoutConfirm")}
      description={t("account.logoutDescription")}
      confirmLabel={busy ? t("account.processing") : t("account.logout")}
      loading={busy}
      errorMessage={error}
      onConfirm={() => void logout()}
      onClose={() => { setConfirmLogout(false); setError(""); }}
    />
  </AccountScreen>;
}

const styles = StyleSheet.create({
  profile: {
    backgroundColor: Colors.softgreen,
    borderRadius: 22,
    padding: 16,
    flexDirection: "row",
    alignItems: "center",
    flexWrap: "wrap",
    gap: 12,
  },
  avatar: {
    width: 54,
    height: 54,
    borderRadius: 27,
    backgroundColor: Colors.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  initial: { color: "#FFFFFF", fontSize: 23, fontFamily: Fonts.pretendardBold },
  identity: { flexGrow: 1, flexShrink: 1, flexBasis: 105, gap: 4 },
  name: { color: "#16352D", fontSize: 21, fontFamily: Fonts.pretendardBold },
  email: { color: "#49635B", fontSize: 13, fontFamily: Fonts.pretendardRegular },
  editButton: {
    minHeight: 44,
    justifyContent: "center",
    paddingHorizontal: 12,
    backgroundColor: "#FFFFFF",
    borderRadius: 12,
  },
  pressedEdit: { opacity: 0.7 },
  editLabel: { color: Colors.primary, fontSize: 13, fontFamily: Fonts.pretendardSemiBold },
  section: { gap: 8 },
  heading: { paddingHorizontal: 4, color: "#54675F", fontSize: 14, fontFamily: Fonts.pretendardSemiBold },
  menu: { borderWidth: 1, borderColor: "#E4EBE7", borderRadius: 18, overflow: "hidden" },
});
