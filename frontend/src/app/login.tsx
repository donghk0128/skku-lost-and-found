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

export default function Login() {
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { setUser } = useAuth();
  const passwordRef = useRef<TextInput>(null);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [focusedField, setFocusedField] = useState<"email" | "password" | null>(
    null,
  );
  const [error, setError] = useState("");

  const handleSignIn = () => {
    if (!email.trim() || !password.trim()) {
      setError("이메일과 비밀번호를 입력해주세요.");
      return;
    }

    Keyboard.dismiss();
    setError("");

    // 임시 로그인: 실제 서버 인증 없이 사용자 상태만 설정
    setUser({
      id: email.trim(),
      name: "임시 사용자",
    });

    router.replace("/");
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
                원활한 서비스 이용을 위해 로그인해주세요.
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
                  onChangeText={(value) => {
                    setEmail(value);
                    setError("");
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
                  onChangeText={(value) => {
                    setPassword(value);
                    setError("");
                  }}
                  onFocus={() => setFocusedField("password")}
                  onBlur={() => setFocusedField(null)}
                  secureTextEntry
                  autoCapitalize="none"
                  autoCorrect={false}
                  autoComplete="current-password"
                  textContentType="password"
                  returnKeyType="go"
                  onSubmitEditing={handleSignIn}
                  accessibilityLabel="비밀번호"
                />
              </View>

              <Text style={styles.error} accessibilityLiveRegion="polite">
                {error || " "}
              </Text>
            </View>
          </View>

          <View style={styles.footer}>
            <Pressable
              onPress={handleSignIn}
              accessibilityRole="button"
              style={({ pressed }) => [
                styles.button,
                pressed && styles.buttonPressed,
              ]}
            >
              <Text style={styles.buttonText}>로그인</Text>
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

              <Pressable disabled style={styles.link}>
                <Text style={styles.linkText}>회원가입</Text>
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
