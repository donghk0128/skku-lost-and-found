import { useRef, useState } from "react";
import { useRouter } from "expo-router";
import {
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
import { useAuth } from "@/providers/AuthProvider";
import { authApi } from "@/lib/auth-api";

export default function Login() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { signIn, signUp, initializationError } = useAuth();
  const passwordRef = useRef<TextInput>(null);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [isSignUp, setIsSignUp] = useState(false);
  const [nickname, setNickname] = useState("");
  const [code, setCode] = useState("");
  const [codeSent, setCodeSent] = useState(false);
  const [verified, setVerified] = useState(false);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [focusedField, setFocusedField] = useState<"email" | "password" | null>(
    null,
  );
  const [error, setError] = useState("");

  const pending = useRef(false);

  const run = async (action: () => Promise<void>) => {
    if (pending.current) return;
    pending.current = true;
    setBusy(true);
    setError("");
    setMessage("");
    Keyboard.dismiss();
    try {
      await action();
    } catch (error) {
      setError(error instanceof Error ? error.message : "요청을 처리하지 못했습니다.");
    } finally {
      pending.current = false;
      setBusy(false);
    }
  };

  const handleSignIn = () => {
    if (pending.current) return;
    if (!email.trim() || !password) {
      setError("이메일과 비밀번호를 입력해주세요.");
      return;
    }

    if (isSignUp && (!verified || nickname.trim().length < 2 || nickname.trim().length > 30 || password.length < 8 || password.length > 128)) {
      setError("이메일 인증을 완료하고 닉네임 2~30자, 비밀번호 8~128자를 입력해주세요.");
      return;
    }
    void run(async () => {
      if (isSignUp) await signUp(email.trim(), nickname.trim(), password);
      else await signIn(email.trim(), password);
      router.replace("/");
    });
  };

  return (
    <KeyboardAvoidingView
      style={styles.root}
      behavior={Platform.OS === "ios" ? "padding" : "height"}
    >
      <ScrollView
        style={styles.scroll}
        contentContainerStyle={[
          styles.content,
          {
            paddingTop: insets.top + 24,
            paddingBottom: Math.max(insets.bottom, 24),
          },
        ]}
        keyboardShouldPersistTaps="handled"
        keyboardDismissMode={Platform.OS === "ios" ? "interactive" : "on-drag"}
        showsVerticalScrollIndicator={false}
        bounces={false}
      >
        <View style={styles.container}>
          <View style={styles.main}>
            <View style={styles.intro}>
              <View style={styles.accent} />

              <Text style={styles.title}>
                안녕하세요,{"\n"}
                성균관대 분실물 찾기{"\n"}
                서비스입니다.
              </Text>

              <Text style={styles.description}>
                {isSignUp ? "학교 이메일 인증 후 회원가입을 진행해주세요." : "원활한 서비스 이용을 위해 로그인해주세요."}
              </Text>
            </View>

            <View style={styles.form}>
              <View style={styles.field}>
                <Text style={styles.label}>이메일</Text>

                <TextInput
                  style={[
                    styles.input,
                    focusedField === "email" && styles.inputFocused,
                  ]}
                  placeholder="이메일을 입력해주세요"
                  placeholderTextColor="#B8BBC0"
                  value={email}
                  editable={!busy}
                  onChangeText={(value) => {
                    setEmail(value);
                    setError("");
                    setMessage("");
                    setCodeSent(false);
                    setVerified(false);
                    setCode("");
                  }}
                  onFocus={() => setFocusedField("email")}
                  onBlur={() => setFocusedField(null)}
                  autoCapitalize="none"
                  autoCorrect={false}
                  keyboardType="email-address"
                  autoComplete="email"
                  textContentType="username"
                  returnKeyType="next"
                  onSubmitEditing={() => passwordRef.current?.focus()}
                  accessibilityLabel="이메일"
                />
              </View>

              {isSignUp && (
                <>
                  <Pressable
                    disabled={busy || !email.trim()}
                    accessibilityRole="button"
                    onPress={() => void run(async () => {
                      const response = await authApi.sendCode(email.trim());
                      setCodeSent(true);
                      setVerified(false);
                      setCode("");
                      setMessage(response.message);
                    })}
                    style={[styles.button, (busy || !email.trim()) && styles.buttonPressed]}
                  >
                    <Text style={styles.buttonText}>{codeSent ? "인증 코드 재전송" : "이메일 인증 코드 전송"}</Text>
                  </Pressable>
                  {codeSent && (
                    <View style={styles.field}>
                      <Text style={styles.label}>이메일 인증 코드</Text>
                      <TextInput
                        style={styles.input}
                        placeholder="6자리 인증 코드"
                        value={code}
                        onChangeText={setCode}
                        editable={!busy && !verified}
                        keyboardType="number-pad"
                        maxLength={6}
                        accessibilityLabel="이메일 인증 코드"
                      />
                      <Pressable
                        disabled={busy || verified || !/^\d{6}$/.test(code)}
                        accessibilityRole="button"
                        onPress={() => void run(async () => {
                          const response = await authApi.verifyCode(email.trim(), code);
                          setVerified(true);
                          setMessage(response.message);
                        })}
                        style={[styles.button, (busy || verified || !/^\d{6}$/.test(code)) && styles.buttonPressed]}
                      >
                        <Text style={styles.buttonText}>{verified ? "이메일 인증 완료" : "인증 코드 확인"}</Text>
                      </Pressable>
                    </View>
                  )}
                  <View style={styles.field}>
                    <Text style={styles.label}>닉네임</Text>
                    <TextInput
                      style={styles.input}
                      placeholder="닉네임 2~30자"
                      value={nickname}
                      onChangeText={setNickname}
                      editable={!busy}
                      maxLength={30}
                      accessibilityLabel="닉네임"
                    />
                  </View>
                </>
              )}

              <View style={styles.field}>
                <Text style={styles.label}>비밀번호</Text>

                <TextInput
                  ref={passwordRef}
                  style={[
                    styles.input,
                    focusedField === "password" && styles.inputFocused,
                  ]}
                  placeholder="비밀번호를 입력해주세요"
                  placeholderTextColor="#B8BBC0"
                  value={password}
                  editable={!busy}
                  onChangeText={(value) => {
                    setPassword(value);
                    setError("");
                  }}
                  onFocus={() => setFocusedField("password")}
                  onBlur={() => setFocusedField(null)}
                  secureTextEntry
                  autoCapitalize="none"
                  autoCorrect={false}
                  autoComplete={isSignUp ? "new-password" : "current-password"}
                  textContentType={isSignUp ? "newPassword" : "password"}
                  returnKeyType="go"
                  onSubmitEditing={handleSignIn}
                  accessibilityLabel="비밀번호"
                />
              </View>

              <Text style={styles.error} accessibilityLiveRegion="polite">
                {error || message || initializationError || " "}
              </Text>
            </View>
          </View>

          <View style={styles.footer}>
            <Pressable
              onPress={handleSignIn}
              disabled={busy}
              accessibilityRole="button"
              style={({ pressed }) => [
                styles.button,
                pressed && styles.buttonPressed,
              ]}
            >
              <Text style={styles.buttonText}>{busy ? "처리 중…" : isSignUp ? "회원가입" : "로그인"}</Text>
            </Pressable>

            <View style={styles.links}>
              {/* 각 기능 구현 전까지 비활성화 */}
              <Pressable disabled style={styles.link}>
                <Text style={styles.linkText}>아이디 찾기</Text>
              </Pressable>

              <View style={styles.divider} />

              <Pressable disabled style={styles.link}>
                <Text style={styles.linkText}>비밀번호 찾기</Text>
              </Pressable>

              <View style={styles.divider} />

              <Pressable disabled={busy} style={styles.link} accessibilityRole="button" onPress={() => {
                setIsSignUp(!isSignUp);
                setPassword("");
                setError("");
                setMessage("");
                setCode("");
                setCodeSent(false);
                setVerified(false);
              }}>
                <Text style={styles.linkText}>{isSignUp ? "로그인으로 돌아가기" : "회원가입"}</Text>
              </Pressable>
            </View>
          </View>
        </View>
      </ScrollView>
    </KeyboardAvoidingView>
  );
}

const styles = StyleSheet.create({
  root: {
    flex: 1,
    backgroundColor: "#FFFFFF",
  },
  scroll: {
    flex: 1,
  },
  content: {
    flexGrow: 1,
    paddingHorizontal: 28,
  },
  container: {
    flex: 1,
    width: "100%",
    maxWidth: 440,
    alignSelf: "center",
  },
  main: {
    paddingTop: 64,
  },
  intro: {
    marginBottom: 36,
  },
  accent: {
    width: 28,
    height: 4,
    borderRadius: 2,
    backgroundColor: Colors.primary,
    marginBottom: 24,
  },
  title: {
    color: "#000000",
    fontSize: 26,
    lineHeight: 38,
    letterSpacing: -0.7,
    fontFamily: Fonts.pretendardSemiBold,
  },
  description: {
    marginTop: 16,
    color: "#9A9DA3",
    fontSize: 14,
    lineHeight: 22,
    fontFamily: Fonts.pretendardRegular,
  },
  form: {
    gap: 22,
  },
  field: {
    gap: 10,
  },
  label: {
    color: "#55585D",
    fontSize: 14,
    fontFamily: Fonts.pretendardMedium,
  },
  input: {
    height: 56,
    borderWidth: 1,
    borderColor: "#DDDEE0",
    borderRadius: 14,
    paddingHorizontal: 18,
    backgroundColor: "#FFFFFF",
    color: "#000000",
    fontSize: 15,
    fontFamily: Fonts.pretendardRegular,
  },
  inputFocused: {
    borderColor: Colors.primary,
  },
  error: {
    marginTop: -10,
    color: "#B54747",
    fontSize: 13,
    lineHeight: 20,
    fontFamily: Fonts.pretendardRegular,
  },
  footer: {
    marginTop: "auto",
    paddingTop: 48,
    paddingBottom: 24,
  },
  button: {
    height: 54,
    borderRadius: 14,
    backgroundColor: Colors.primary,
    alignItems: "center",
    justifyContent: "center",
  },
  buttonPressed: {
    opacity: 0.85,
  },
  buttonText: {
    color: "#FFFFFF",
    fontSize: 16,
    fontFamily: Fonts.pretendardSemiBold,
  },
  links: {
    flexDirection: "row",
    flexWrap: "wrap",
    alignItems: "center",
    justifyContent: "center",
    marginTop: 20,
  },
  link: {
    minHeight: 44,
    paddingHorizontal: 8,
    justifyContent: "center",
  },
  linkText: {
    color: "#9A9DA3",
    fontSize: 12,
    fontFamily: Fonts.pretendardRegular,
  },
  divider: {
    width: 1,
    height: 11,
    backgroundColor: "#DDDEE0",
  },
});
