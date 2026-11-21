import { useRef, useState } from "react";
import { useRouter } from "expo-router";
import { Text } from "react-native";
import { AccountButton, AccountError, AccountField, AccountScreen, accountStyles as s } from "@/components/account-screen";
import { accountApi } from "@/lib/account-api";
import { useAuth } from "@/providers/AuthProvider";
import { useLocale } from "@/i18n/LocaleProvider";

export default function ProfileEdit() {
  const { user, updateUser } = useAuth();
  const { t } = useLocale();
  const router = useRouter();
  const [nickname, setNickname] = useState(user?.nickname ?? "");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const pending = useRef(false);
  const back = () => router.canGoBack() ? router.back() : router.replace("/(tabs)/account");
  const save = async () => {
    if (pending.current) return;
    const clean = nickname.normalize("NFKC").trim();
    if (Array.from(clean).length < 2 || Array.from(clean).length > 30) { setError(t("account.nicknameRule")); return; }
    pending.current = true; setBusy(true); setError("");
    try { updateUser(await accountApi.updateProfile(clean)); back(); }
    catch (e) { setError(e instanceof Error ? e.message : t("common.requestFailed")); }
    finally { pending.current = false; setBusy(false); }
  };
  return <AccountScreen title={t("account.editProfile")} busy={busy} footer={<>
    <AccountButton label={busy ? t("account.processing") : t("account.save")} disabled={busy} onPress={() => void save()} />
    <AccountButton label={t("common.cancel")} secondary disabled={busy} onPress={back} />
  </>}>
    <AccountField label={t("account.nickname")} value={nickname} onChangeText={setNickname} editable={!busy} maxLength={30} />
    <Text style={s.copy}>{t("account.nicknameRule")}</Text>
    <AccountButton label={t("account.changePassword")} secondary disabled={busy} onPress={() => router.push("/password-change")} />
    <AccountError message={error} />
  </AccountScreen>;
}
