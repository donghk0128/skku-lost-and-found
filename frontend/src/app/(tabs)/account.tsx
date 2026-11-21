import { useRef, useState } from "react";
import { useRouter } from "expo-router";
import { Modal, Pressable, Text, View } from "react-native";
import { AccountButton, AccountError, AccountScreen, accountStyles as s } from "@/components/account-screen";
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
  return <AccountScreen title={t("tabs.account")} tab>
    <View style={s.card}>
      <Text style={s.title}>{user?.nickname}</Text>
      <Text selectable style={s.copy}>{user?.email}</Text>
    </View>
    <Pressable accessibilityRole="button" style={s.row} onPress={() => router.push("/profile-edit")}>
      <Text style={s.rowLabel}>{t("account.editProfile")}</Text><Text>›</Text>
    </Pressable>
    <Pressable accessibilityRole="button" accessibilityState={{ disabled: true }} disabled style={s.row}>
      <Text style={[s.rowLabel, { color: "#87928C" }]}>{t("account.keywords")}</Text>
      <Text style={s.placeholder}>{t("account.comingSoon")}</Text>
    </Pressable>
    <Pressable accessibilityRole="button" style={s.row} onPress={() => router.push("/my-posts")}>
      <Text style={s.rowLabel}>{t("account.myPosts")}</Text><Text>›</Text>
    </Pressable>
    <Pressable accessibilityRole="button" style={s.row} onPress={() => router.push("/favorites")}>
      <Text style={s.rowLabel}>{t("account.favorites")}</Text><Text>›</Text>
    </Pressable>
    <Pressable accessibilityRole="button" style={s.row} onPress={() => setConfirmLogout(true)}>
      <Text style={s.rowLabel}>{t("account.logout")}</Text><Text>›</Text>
    </Pressable>
    <Pressable accessibilityRole="button" style={s.row} onPress={() => router.push("/withdrawal")}>
      <Text style={[s.rowLabel, { color: "#A74747" }]}>{t("account.withdraw")}</Text><Text>›</Text>
    </Pressable>
    <Modal transparent visible={confirmLogout} animationType="fade" onRequestClose={() => { if (!busy) setConfirmLogout(false); }}>
      <View style={{ flex: 1, backgroundColor: "rgba(0,0,0,0.35)", justifyContent: "center", padding: 24 }}>
        <View accessibilityViewIsModal style={[s.card, { maxWidth: 420, width: "100%", alignSelf: "center" }]}>
          <Text style={s.label}>{t("account.logoutConfirm")}</Text>
          <AccountError message={error} />
          <AccountButton label={busy ? t("account.processing") : t("account.logout")} disabled={busy} onPress={() => void logout()} />
          <AccountButton label={t("common.cancel")} secondary disabled={busy} onPress={() => { setConfirmLogout(false); setError(""); }} />
        </View>
      </View>
    </Modal>
  </AccountScreen>;
}
