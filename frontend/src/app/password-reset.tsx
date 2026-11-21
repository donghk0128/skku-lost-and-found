import { useRef, useState } from "react";
import { useRouter } from "expo-router";
import { KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet, Text, TextInput, View } from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Colors, Fonts } from "@/constants/theme";
import { authApi } from "@/lib/auth-api";
import { isValidSignupPassword } from "@/lib/password-validation";
import { useLocale } from "@/i18n/LocaleProvider";

export default function PasswordReset() {
  const { t } = useLocale();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const [stage, setStage] = useState<"email" | "code" | "password">("email");
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [token, setToken] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [error, setError] = useState("");
  const [busy, setBusy] = useState(false);
  const pending = useRef(false);
  const submit = async () => {
    if (pending.current) return;
    if (!email.trim()) { setError(t("signup.emailRequired")); return; }
    if (stage === "code" && !/^\d{6}$/.test(code)) { setError(t("signup.codeRequired")); return; }
    if (stage === "password") {
      if (!isValidSignupPassword(password)) { setError(t("reset.passwordRule")); return; }
      if (password !== confirmation) { setError(t("signup.passwordMismatch")); return; }
    }
    pending.current = true; setBusy(true); setError("");
    try {
      const address = email.trim();
      if (stage === "email") { await authApi.sendPasswordResetCode(address); setStage("code"); }
      else if (stage === "code") { const result = await authApi.verifyPasswordResetCode(address, code); setToken(result.reset_token); setStage("password"); }
      else { await authApi.completePasswordReset(address, token, password, confirmation); router.replace({ pathname: "/login", params: { resetDone: "1" } }); }
    } catch (caught) { setError(caught instanceof Error ? caught.message : t("common.requestFailed")); }
    finally { pending.current = false; setBusy(false); }
  };
  return <KeyboardAvoidingView style={styles.root} behavior={Platform.OS === "ios" ? "padding" : "height"}>
    <ScrollView contentContainerStyle={[styles.content, { paddingTop: insets.top + 36, paddingBottom: insets.bottom + 32 }]} keyboardShouldPersistTaps="handled">
      <View style={styles.container}>
        <Pressable accessibilityRole="button" onPress={() => router.back()}><Text style={styles.back}>‹  {t("common.back")}</Text></Pressable>
        <Text style={styles.title}>{t("reset.title")}</Text>
        <Text style={styles.hint}>{t("reset.hint")}</Text>
        <Text style={styles.label}>{t("login.email")}</Text>
        <TextInput style={styles.input} accessibilityLabel={t("login.email")} value={email} onChangeText={setEmail} editable={stage === "email" && !busy} keyboardType="email-address" autoCapitalize="none" autoComplete="email" />
        {stage !== "email" && <><Text style={styles.label}>{t("withdrawal.code")}</Text><TextInput style={styles.input} accessibilityLabel={t("withdrawal.code")} value={code} onChangeText={setCode} editable={stage === "code" && !busy} keyboardType="number-pad" maxLength={6} /></>}
        {stage === "password" && <>
          <Text style={styles.label}>{t("account.newPassword")}</Text><TextInput style={styles.input} accessibilityLabel={t("account.newPassword")} value={password} onChangeText={setPassword} secureTextEntry autoComplete="new-password" maxLength={20} editable={!busy} />
          <Text style={styles.label}>{t("account.confirmPassword")}</Text><TextInput style={styles.input} accessibilityLabel={t("account.confirmPassword")} value={confirmation} onChangeText={setConfirmation} secureTextEntry autoComplete="new-password" maxLength={20} editable={!busy} />
          <Text style={styles.hint}>{t("reset.passwordRule")}</Text>
        </>}
        <Text style={styles.error} accessibilityLiveRegion="polite">{error}</Text>
        <Pressable style={styles.button} accessibilityRole="button" disabled={busy} onPress={submit}><Text style={styles.buttonText}>{busy ? t("common.processing") : t(stage === "email" ? "reset.send" : stage === "code" ? "reset.verify" : "reset.complete")}</Text></Pressable>
        {stage === "code" && <Pressable accessibilityRole="button" disabled={busy} onPress={async () => {
          if (pending.current) return;
          pending.current = true; setBusy(true); setError("");
          try { await authApi.sendPasswordResetCode(email.trim()); setCode(""); }
          catch (caught) { setError(caught instanceof Error ? caught.message : t("common.requestFailed")); }
          finally { pending.current = false; setBusy(false); }
        }}><Text style={styles.resend}>{t("withdrawal.resend")}</Text></Pressable>}
      </View>
    </ScrollView>
  </KeyboardAvoidingView>;
}

const styles = StyleSheet.create({ root: { flex: 1, backgroundColor: "#fff" }, content: { flexGrow: 1, paddingHorizontal: 28 }, container: { width: "100%", maxWidth: 440, alignSelf: "center" }, back: { fontSize: 18, color: Colors.primary, marginBottom: 42 }, title: { fontSize: 26, fontFamily: Fonts.pretendardSemiBold }, hint: { marginTop: 14, marginBottom: 25, color: "#888", fontSize: 14 }, label: { marginTop: 15, marginBottom: 9, fontFamily: Fonts.pretendardMedium }, input: { height: 55, borderWidth: 1, borderColor: "#DDDEE0", borderRadius: 14, paddingHorizontal: 18, fontSize: 15 }, error: { color: "#B54747", minHeight: 30, marginTop: 12 }, button: { height: 54, borderRadius: 14, backgroundColor: Colors.primary, alignItems: "center", justifyContent: "center" }, buttonText: { color: "#fff", fontSize: 16, fontFamily: Fonts.pretendardSemiBold }, resend: { textAlign: "center", color: Colors.primary, padding: 18 } });
