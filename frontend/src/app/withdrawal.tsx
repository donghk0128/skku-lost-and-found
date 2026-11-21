import { useEffect, useRef, useState } from "react";
import { useRouter } from "expo-router";
import { AppState, Text, View } from "react-native";
import { AccountButton, AccountError, AccountField, AccountScreen, accountStyles as s } from "@/components/account-screen";
import { accountApi } from "@/lib/account-api";
import { ApiError } from "@/lib/auth-api";
import { useAuth } from "@/providers/AuthProvider";
import { useLocale } from "@/i18n/LocaleProvider";

export default function Withdrawal() {
  const { user, clearAccount } = useAuth();
  const { t } = useLocale();
  const router = useRouter();
  const [stage, setStage] = useState<"password" | "email">("password");
  const [password, setPassword] = useState("");
  const [token, setToken] = useState("");
  const [code, setCode] = useState("");
  const [proofDeadline, setProofDeadline] = useState(0);
  const [codeDeadline, setCodeDeadline] = useState(0);
  const [resendAt, setResendAt] = useState(0);
  const [now, setNow] = useState(Date.now);
  const [verified, setVerified] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const pending = useRef(false);
  useEffect(() => {
    const update = () => setNow(Date.now());
    const timer = setInterval(update, 1000);
    const subscription = AppState.addEventListener("change", state => { if (state === "active") update(); });
    return () => { clearInterval(timer); subscription.remove(); };
  }, []);
  const proofExpired = stage === "email" && now >= proofDeadline;
  const codeExpired = codeDeadline > 0 && now >= codeDeadline;
  const seconds = Math.max(0, Math.ceil((Math.min(proofDeadline, codeDeadline || Infinity) - now) / 1000));
  const resendSeconds = Math.max(0, Math.ceil((resendAt - now) / 1000));
  const run = async (action: () => Promise<void>) => {
    if (pending.current) return;
    pending.current = true; setBusy(true); setError("");
    try { await action(); }
    catch (e) { setError(e instanceof Error ? e.message : t("common.requestFailed")); }
    finally { pending.current = false; setBusy(false); }
  };
  const start = () => void run(async () => {
    if (!password) throw new Error(t("account.currentPasswordRequired"));
    const result = await accountApi.startWithdrawal(password);
    setPassword(""); setToken(result.withdrawal_token); setProofDeadline(Date.parse(result.expires_at));
    setCode(""); setCodeDeadline(0); setVerified(false); setResendAt(0); setStage("email");
  });
  const send = () => void run(async () => {
    const result = await accountApi.sendWithdrawalCode(token);
    setCode(""); setVerified(false); setCodeDeadline(Date.parse(result.expires_at)); setResendAt(Date.parse(result.resend_available_at));
  });
  const verify = () => void run(async () => {
    if (!/^\d{6}$/.test(code)) throw new Error(t("signup.codeRequired"));
    const result = await accountApi.verifyWithdrawalEmail(token, code);
    setCodeDeadline(Date.parse(result.expires_at)); setVerified(true); setCode("");
  });
  const withdraw = () => void run(async () => {
    if (!verified || proofExpired || codeExpired) return;
    try { await accountApi.withdraw(token); }
    catch (e) {
      // A retry after an already-committed deletion can only see an invalid login.
      if (!(e instanceof ApiError) || e.status !== 401) throw e;
    }
    setToken("");
    await clearAccount();
  });
  const cancel = () => router.replace("/(tabs)/account");
  return <AccountScreen title={t(stage === "password" ? "withdrawal.passwordTitle" : "account.withdraw")} busy={busy} footer={<>
    <AccountButton label={busy ? t("account.processing") : t(stage === "password" ? "withdrawal.next" : "withdrawal.submit")}
      onPress={stage === "password" ? start : withdraw} danger={stage === "email"}
      disabled={busy || (stage === "email" && (!verified || proofExpired || codeExpired))} />
    <AccountButton label={t("common.cancel")} secondary disabled={busy} onPress={cancel} />
  </>}>
    {stage === "password" ? <>
      <Text style={s.copy}>{t("withdrawal.passwordHint")}</Text>
      <AccountField label={t("account.currentPassword")} value={password} onChangeText={setPassword}
        secureTextEntry autoComplete="current-password" maxLength={128} editable={!busy} />
    </> : <>
      <View style={s.card}><Text style={s.label}>{t("withdrawal.noticeTitle")}</Text>
        <Text style={s.copy}>{t("withdrawal.notice")}</Text>
      </View>
      <AccountField label={t("login.email")} value={user?.email ?? ""} editable={false} />
      <Text style={s.copy}>{t("withdrawal.emailHint")}</Text>
      {!verified || codeExpired ? <>
        <AccountButton label={resendSeconds ? t("withdrawal.resendWait", { count: resendSeconds }) : t(codeDeadline ? "withdrawal.resend" : "withdrawal.send")}
          secondary disabled={busy || proofExpired || resendSeconds > 0} onPress={send} />
        {codeDeadline > 0 && <>
          <AccountField label={t("withdrawal.code")} value={code} onChangeText={setCode} keyboardType="number-pad"
            autoComplete="one-time-code" maxLength={6} editable={!busy && !proofExpired && !codeExpired} />
          <AccountButton label={t("withdrawal.verify")} secondary disabled={busy || proofExpired || codeExpired || !/^\d{6}$/.test(code)} onPress={verify} />
        </>}
      </> : <Text accessibilityLiveRegion="polite" style={s.label}>{t("withdrawal.verified")}</Text>}
      {proofExpired || codeExpired
        ? <Text accessibilityRole="alert" style={s.error}>{t("withdrawal.expired")}</Text>
        : <Text style={s.copy}>{t("withdrawal.remaining", { count: seconds })}</Text>}
      <AccountButton label={t("withdrawal.restart")} secondary disabled={busy} onPress={() => {
        setToken(""); setCode(""); setVerified(false); setError(""); setStage("password");
      }} />
    </>}
    <AccountError message={error} />
  </AccountScreen>;
}
