import { useRef, useState } from "react";
import { useRouter } from "expo-router";
import { Text, View } from "react-native";
import { AccountButton, AccountError, AccountField, AccountScreen, accountStyles as s } from "@/components/account-screen";
import { accountApi } from "@/lib/account-api";
import { useLocale } from "@/i18n/LocaleProvider";

export default function PasswordChange() {
  const { t } = useLocale();
  const router = useRouter();
  const [currentPassword, setCurrentPassword] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [busy, setBusy] = useState(false);
  const [done, setDone] = useState(false);
  const [error, setError] = useState("");
  const pending = useRef(false);
  const back = () => router.canGoBack() ? router.back() : router.replace("/profile-edit");
  const save = async () => {
    if (pending.current) return;
    setError("");
    if (!currentPassword) { setError(t("account.currentPasswordRequired")); return; }
    if (Array.from(password).length < 8 || Array.from(password).length > 128) { setError(t("account.passwordRule")); return; }
    if (password !== confirmation) { setError(t("signup.passwordMismatch")); return; }
    pending.current = true; setBusy(true);
    try {
      await accountApi.changePassword(currentPassword, password, confirmation);
      setCurrentPassword(""); setPassword(""); setConfirmation(""); setDone(true);
    } catch (e) { setError(e instanceof Error ? e.message : t("common.requestFailed")); }
    finally { pending.current = false; setBusy(false); }
  };
  return <AccountScreen title={t("account.changePassword")} busy={busy} footer={<>
    <AccountButton label={done ? t("account.confirm") : busy ? t("account.processing") : t("account.completePassword")} disabled={busy} onPress={done ? back : () => void save()} />
    {!done && <AccountButton label={t("common.cancel")} secondary disabled={busy} onPress={back} />}
  </>}>
    {done ? <View style={s.card}>
      <Text accessibilityLiveRegion="polite" style={s.label}>{t("account.passwordDone")}</Text>
      <Text style={s.copy}>{t("account.stillSignedIn")}</Text>
    </View> : <>
      <AccountField label={t("account.currentPassword")} value={currentPassword} onChangeText={setCurrentPassword} secureTextEntry autoComplete="current-password" editable={!busy} maxLength={128} />
      <AccountField label={t("account.newPassword")} value={password} onChangeText={setPassword} secureTextEntry autoComplete="new-password" editable={!busy} maxLength={128} />
      <AccountField label={t("account.confirmPassword")} value={confirmation} onChangeText={setConfirmation} secureTextEntry autoComplete="new-password" editable={!busy} maxLength={128} />
      <Text style={s.copy}>{t("account.passwordRule")}</Text><AccountError message={error} />
    </>}
  </AccountScreen>;
}
