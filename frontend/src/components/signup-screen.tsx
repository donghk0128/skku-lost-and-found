import { useCallback, useEffect, useRef, useState } from "react";
import { useFocusEffect, useLocalSearchParams, useRouter } from "expo-router";
import {
  AppState,
  Keyboard,
  KeyboardAvoidingView,
  Platform,
  Pressable,
  ScrollView,
  StyleSheet,
  Text,
  TextInput,
  View,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";

import { Colors, Fonts } from "@/constants/theme";
import { authApi } from "@/lib/auth-api";
import { useAuth } from "@/providers/AuthProvider";

type Stage = "email" | "code" | "information";

function FieldError({ message }: { message: string }) {
  if (!message) return null;
  return (
    <View
      style={styles.errorRow}
      accessibilityRole="alert"
      accessibilityLiveRegion="polite"
    >
      <View style={styles.infoIcon} accessible={false}>
        <Text style={styles.infoIconText}>i</Text>
      </View>
      <Text style={styles.fieldError}>{message}</Text>
    </View>
  );
}

export default function SignupScreen({ stage }: { stage: Stage }) {
  const router = useRouter();
  const { signUp } = useAuth();
  const insets = useSafeAreaInsets();
  const params = useLocalSearchParams<{ email?: string; expiresAt?: string }>();
  const verificationEmail =
    typeof params.email === "string" ? params.email : "";
  const expiresAt = Number(params.expiresAt);
  const [remaining, setRemaining] = useState(300);
  const active = useRef(true);
  const expired = useRef(false);
  const returnToMain = useCallback(() => {
    if (expired.current) return;
    expired.current = true;
    Keyboard.dismiss();
    router.dismissAll();
    router.replace("/");
  }, [router]);

  useFocusEffect(
    useCallback(() => {
      active.current = true;
      if (stage !== "code")
        return () => {
          active.current = false;
        };
      const update = () => {
        const seconds = Math.max(0, Math.ceil((expiresAt - Date.now()) / 1000));
        setRemaining(Number.isFinite(seconds) ? seconds : 0);
        if (!verificationEmail || !Number.isFinite(expiresAt) || seconds <= 0)
          returnToMain();
      };
      update();
      const interval = setInterval(update, 250);
      const subscription = AppState.addEventListener("change", (state) => {
        if (state === "active") update();
      });
      return () => {
        active.current = false;
        clearInterval(interval);
        subscription.remove();
      };
    }, [stage, expiresAt, verificationEmail, returnToMain]),
  );
  const [email, setEmail] = useState("");
  const [code, setCode] = useState("");
  const [id, setId] = useState("");
  const [password, setPassword] = useState("");
  const [confirmation, setConfirmation] = useState("");
  const [focused, setFocused] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [error, setError] = useState("");
  const [touched, setTouched] = useState({
    id: false,
    password: false,
    confirmation: false,
  });
  const nickname = id.normalize("NFKC").trim();
  const idError =
    Array.from(nickname).length < 2 || Array.from(nickname).length > 10
      ? "아이디는 2~10자로 입력해주세요."
      : "";
  const passwordLength = Array.from(password).length;
  const passwordError =
    passwordLength < 8 ||
    passwordLength > 20 ||
    !/[A-Za-z]/.test(password) ||
    !/[0-9]/.test(password)
      ? "비밀번호는 영문과 숫자를 포함한 8~20자로 입력해주세요."
      : "";
  const confirmationError = !confirmation
    ? "비밀번호를 다시 입력해주세요."
    : password !== confirmation
      ? "비밀번호가 일치하지 않습니다."
      : "";
  const pending = useRef(false);
  const mounted = useRef(true);
  useEffect(() => {
    mounted.current = true;
    return () => {
      mounted.current = false;
    };
  }, []);
  const information = stage === "information";

  const back = () => {
    Keyboard.dismiss();
    if (router.canGoBack()) router.back();
    else
      router.replace(
        stage === "information"
          ? "/signup-code"
          : stage === "code"
            ? "/signup"
            : "/login",
      );
  };

  const next = async () => {
    Keyboard.dismiss();
    setFocused(null);
    if (pending.current) return;
    if (stage === "code" && (expired.current || Date.now() >= expiresAt)) {
      returnToMain();
      return;
    }
    const address = stage === "email" ? email.trim() : verificationEmail;
    if (!address) {
      setError("학교 이메일을 입력해주세요.");
      return;
    }
    if (stage === "code" && !/^\d{6}$/.test(code)) {
      setError("6자리 숫자 인증 코드를 입력해주세요.");
      return;
    }
    if (stage === "information") {
      setTouched({ id: true, password: true, confirmation: true });
      setError("");
      if (idError || passwordError || confirmationError) return;
    }
    pending.current = true;
    setSending(true);
    setError("");
    try {
      if (stage === "email") {
        const deadline = Date.now() + 5 * 60 * 1000;
        await authApi.sendCode(address);
        if (mounted.current && active.current)
          router.push({
            pathname: "/signup-code",
            params: { email: address, expiresAt: String(deadline) },
          });
      } else if (stage === "information") {
        await signUp(address, nickname, password);
        router.replace("/");
      } else {
        await authApi.verifyCode(address, code);
        if (mounted.current && active.current && !expired.current) {
          if (Date.now() >= expiresAt) returnToMain();
          else
            router.replace({
              pathname: "/signup-information",
              params: { email: address },
            });
        }
      }
    } catch (error) {
      if (mounted.current && active.current && !expired.current)
        setError(
          error instanceof Error
            ? error.message
            : "요청을 처리하지 못했습니다.",
        );
    } finally {
      pending.current = false;
      if (mounted.current) setSending(false);
    }
  };

  return (
    <KeyboardAvoidingView
      style={styles.root}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
    >
      <ScrollView
        contentContainerStyle={[
          styles.content,
          { paddingTop: insets.top + 20, paddingBottom: insets.bottom + 32 },
        ]}
        keyboardShouldPersistTaps="handled"
        showsVerticalScrollIndicator={false}
      >
        <View style={styles.container}>
          <Pressable
            onPress={back}
            accessibilityRole="button"
            accessibilityLabel="이전 단계"
            hitSlop={8}
            style={styles.back}
          >
            <View style={styles.chevron} />
          </Pressable>
          <View style={styles.main}>
            <View
              style={styles.steps}
              accessibilityLabel={`회원가입 ${information ? 2 : 1}단계, 총 2단계`}
            >
              <View
                style={[styles.circle, !information && styles.activeCircle]}
              >
                <Text
                  style={[styles.stepText, !information && styles.activeText]}
                >
                  1
                </Text>
              </View>
              <View style={styles.connector} />
              <View style={[styles.circle, information && styles.activeCircle]}>
                <Text
                  style={[styles.stepText, information && styles.activeText]}
                >
                  2
                </Text>
              </View>
            </View>
            <Text style={styles.title}>
              {information ? "Information" : "Verification"}
            </Text>

            {information ? (
              <View style={styles.informationForm}>
                <View style={styles.field}>
                  <Text style={styles.label}>ID</Text>
                  <TextInput
                    accessibilityLabel="ID"
                    style={[
                      styles.input,
                      focused === "id" && styles.focused,
                      touched.id && idError ? styles.inputError : null,
                    ]}
                    placeholder="아이디 2~10자"
                    placeholderTextColor="#D0D0D0"
                    value={id}
                    editable={!sending}
                    onChangeText={(value) => {
                      setId(value);
                      setTouched((previous) => ({ ...previous, id: true }));
                      setError("");
                    }}
                    autoCapitalize="none"
                    autoCorrect={false}
                    onFocus={() => setFocused("id")}
                    onBlur={() => setFocused(null)}
                  />
                  <FieldError message={touched.id ? idError : ""} />
                </View>
                <View style={styles.field}>
                  <Text style={styles.label}>Password</Text>
                  <TextInput
                    accessibilityLabel="Password"
                    style={[
                      styles.input,
                      focused === "password" && styles.focused,
                      touched.password && passwordError
                        ? styles.inputError
                        : null,
                    ]}
                    placeholder="영문·숫자 포함 8~20자"
                    placeholderTextColor="#D0D0D0"
                    value={password}
                    editable={!sending}
                    onChangeText={(value) => {
                      setPassword(value);
                      setTouched((previous) => ({
                        ...previous,
                        password: true,
                      }));
                      setError("");
                    }}
                    secureTextEntry
                    autoCapitalize="none"
                    autoComplete="new-password"
                    onFocus={() => setFocused("password")}
                    onBlur={() => setFocused(null)}
                  />
                  <FieldError message={touched.password ? passwordError : ""} />
                </View>
                <View style={styles.field}>
                  <Text style={styles.label}>Confirm Password</Text>
                  <TextInput
                    accessibilityLabel="Confirm Password"
                    style={[
                      styles.input,
                      focused === "confirmation" && styles.focused,
                      touched.confirmation && confirmationError
                        ? styles.inputError
                        : null,
                    ]}
                    placeholder="Enter your password"
                    placeholderTextColor="#D0D0D0"
                    value={confirmation}
                    editable={!sending}
                    onChangeText={(value) => {
                      setConfirmation(value);
                      setTouched((previous) => ({
                        ...previous,
                        confirmation: true,
                      }));
                      setError("");
                    }}
                    secureTextEntry
                    autoCapitalize="none"
                    autoComplete="new-password"
                    onFocus={() => setFocused("confirmation")}
                    onBlur={() => setFocused(null)}
                  />
                  <FieldError
                    message={touched.confirmation ? confirmationError : ""}
                  />
                </View>
                <FieldError message={error} />
              </View>
            ) : (
              <View style={styles.verificationForm}>
                <Text style={styles.description}>
                  {stage === "email"
                    ? "Enter your SKK University email address."
                    : "Verification code has sent to your email."}
                </Text>
                <Text style={styles.hint}>
                  {stage === "email"
                    ? "ex) @g.skku.edu, @skku.edu"
                    : "Please check your email box."}
                </Text>
                {stage === "email" ? (
                  <TextInput
                    accessibilityLabel="학교 이메일"
                    style={[
                      styles.input,
                      styles.verificationInput,
                      focused === "email" && styles.focused,
                    ]}
                    placeholder="example@g.skku.edu"
                    placeholderTextColor="#D0D0D0"
                    value={email}
                    editable={!sending}
                    onChangeText={(value) => {
                      setEmail(value);
                      setError("");
                    }}
                    keyboardType="email-address"
                    autoCapitalize="none"
                    autoCorrect={false}
                    autoComplete="email"
                    onFocus={() => setFocused("email")}
                    onBlur={() => setFocused(null)}
                  />
                ) : (
                  <View
                    style={[
                      styles.codeBox,
                      styles.verificationInput,
                      focused === "code" && styles.focused,
                    ]}
                  >
                    <TextInput
                      accessibilityLabel="6자리 인증 코드"
                      style={styles.codeInput}
                      placeholder="000000"
                      placeholderTextColor="#D0D0D0"
                      value={code}
                      editable={!sending}
                      onChangeText={(value) => {
                        setCode(value.replace(/\D/g, ""));
                        setError("");
                      }}
                      keyboardType="number-pad"
                      maxLength={6}
                      onFocus={() => setFocused("code")}
                      onBlur={() => setFocused(null)}
                    />
                    <Text
                      style={styles.timer}
                      accessibilityLabel={`인증 남은 시간 ${remaining}초`}
                    >{`${Math.floor(remaining / 60)}:${String(remaining % 60).padStart(2, "0")}`}</Text>
                  </View>
                )}
                <FieldError message={error} />
              </View>
            )}

            <Pressable
              accessibilityRole="button"
              accessibilityLabel={
                information
                  ? "Sign Up"
                  : stage === "email"
                    ? "Send Code"
                    : "Verify"
              }
              accessibilityState={{ disabled: sending, busy: sending }}
              disabled={sending}
              onPress={() => void next()}
              style={({ pressed }) => [
                styles.button,
                information ? styles.signupButton : styles.verifyButton,
                (pressed || sending) && styles.pressed,
              ]}
            >
              <Text style={styles.buttonText}>
                {sending
                  ? information
                    ? "Signing up…"
                    : stage === "code"
                      ? "Verifying…"
                      : "Sending…"
                  : information
                    ? "Sign Up"
                    : stage === "email"
                      ? "Send Code"
                      : "Verify"}
              </Text>
            </Pressable>
          </View>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#FFFFFF" },
  content: { flexGrow: 1, paddingHorizontal: 32 },
  container: { width: "100%", maxWidth: 400, alignSelf: "center" },
  back: {
    width: 44,
    height: 44,
    justifyContent: "center",
    alignItems: "center",
    marginLeft: -20,
  },
  chevron: {
    width: 10,
    height: 10,
    borderLeftWidth: 2,
    borderBottomWidth: 2,
    borderColor: "#202020",
    transform: [{ rotate: "45deg" }],
  },
  main: { paddingTop: 42, paddingHorizontal: 4 },
  steps: { flexDirection: "row", alignItems: "center" },
  circle: {
    width: 30,
    height: 30,
    borderRadius: 15,
    borderWidth: 1,
    borderColor: "#C6C6C6",
    alignItems: "center",
    justifyContent: "center",
  },
  activeCircle: {
    backgroundColor: Colors.primary,
    borderColor: Colors.primary,
  },
  stepText: {
    fontFamily: Fonts.pretendardRegular,
    fontSize: 14,
    color: "#A5A5A5",
  },
  activeText: { color: "#FFFFFF" },
  connector: { width: 16, height: 1, backgroundColor: "#C6C6C6" },
  title: {
    marginTop: 26,
    fontSize: 28,
    letterSpacing: -1,
    fontFamily: Fonts.pretendardMedium,
    color: "#000000",
  },
  verificationForm: { marginTop: 128 },
  description: {
    fontFamily: Fonts.pretendardMedium,
    fontSize: 15,
    lineHeight: 22,
    letterSpacing: -0.5,
    color: "#000000",
  },
  hint: {
    marginTop: 8,
    fontFamily: Fonts.pretendardRegular,
    fontSize: 14,
    lineHeight: 20,
    letterSpacing: -0.4,
    color: "#999999",
  },
  verificationInput: { marginTop: 22 },
  input: {
    height: 50,
    borderWidth: 1,
    borderColor: "#D6D6D6",
    borderRadius: 14,
    paddingHorizontal: 20,
    fontSize: 14,
    fontFamily: Fonts.pretendardRegular,
    color: "#111111",
    backgroundColor: "#FFFFFF",
  },
  focused: { borderColor: Colors.primary },
  inputError: { borderColor: "#B54747" },
  errorRow: {
    flexDirection: "row",
    alignItems: "flex-start",
    gap: 6,
    marginTop: 2,
  },
  infoIcon: {
    width: 15,
    height: 15,
    borderRadius: 8,
    borderWidth: 1,
    borderColor: "#B54747",
    alignItems: "center",
    justifyContent: "center",
    marginTop: 2,
    flexShrink: 0,
  },
  infoIconText: {
    color: "#B54747",
    fontSize: 10,
    lineHeight: 12,
    fontFamily: Fonts.pretendardSemiBold,
  },
  fieldError: {
    flex: 1,
    color: "#B54747",
    fontSize: 13,
    lineHeight: 20,
    fontFamily: Fonts.pretendardRegular,
  },
  codeBox: {
    height: 50,
    borderWidth: 1,
    borderColor: "#D6D6D6",
    borderRadius: 14,
    flexDirection: "row",
    alignItems: "center",
    paddingHorizontal: 20,
  },
  codeInput: {
    flex: 1,
    height: "100%",
    fontFamily: Fonts.pretendardRegular,
    fontSize: 14,
    color: "#111111",
  },
  timer: {
    color: "#FF5757",
    fontFamily: Fonts.pretendardRegular,
    fontSize: 14,
    marginLeft: 12,
  },
  informationForm: { marginTop: 46, gap: 24 },
  field: { gap: 8 },
  label: { fontFamily: Fonts.pretendardMedium, fontSize: 14, color: "#000000" },
  button: {
    height: 49,
    backgroundColor: Colors.primary,
    borderRadius: 13,
    alignItems: "center",
    justifyContent: "center",
  },
  verifyButton: { marginTop: 76 },
  signupButton: { marginTop: 70 },
  buttonText: {
    fontFamily: Fonts.pretendardMedium,
    fontSize: 14,
    color: "#FFFFFF",
  },
  error: {
    marginTop: 12,
    color: "#B54747",
    fontSize: 13,
    lineHeight: 20,
    fontFamily: Fonts.pretendardRegular,
  },
  pressed: { opacity: 0.8 },
});
