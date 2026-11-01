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
import { useLocale } from "@/i18n/LocaleProvider";
import LanguageSelector from "@/components/language-selector";

export default function Login() {
  const { t } = useLocale();
  const router = useRouter();
  const insets = useSafeAreaInsets();
  const { signIn, initializationError } = useAuth();
  const passwordRef = useRef<TextInput>(null);

  const [email, setEmail] = useState("");
  const [password, setPassword] = useState("");
  const [busy, setBusy] = useState(false);
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
    Keyboard.dismiss();
    try {
      await action();
    } catch (error) {
      setError(error instanceof Error ? error.message : t("common.requestFailed"));
    } finally {
      pending.current = false;
      setBusy(false);
    }
  };

  const handleSignIn = () => {
    if (pending.current) return;
    if (!email.trim() || !password) {
      setError(t("login.missingCredentials"));
      return;
    }

    void run(async () => {
      await signIn(email.trim(), password);
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
                {t("login.greeting")}
                {"\n"}
                {t("login.serviceName")}
              </Text>

              <Text style={styles.description}>
                {t("login.serviceDescription")}
              </Text>
            </View>

            <View style={styles.form}>
              <View style={styles.field}>
                <Text style={styles.label}>{t("login.email")}</Text>

                <TextInput
                  style={[
                    styles.input,
                    focusedField === "email" && styles.inputFocused,
                  ]}
                  placeholder={t("login.emailPlaceholder")}
                  placeholderTextColor="#B8BBC0"
                  value={email}
                  editable={!busy}
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
                  accessibilityLabel={t("login.email")}
                />
              </View>

              <View style={styles.field}>
                <Text style={styles.label}>{t("login.password")}</Text>

                <TextInput
                  ref={passwordRef}
                  style={[
                    styles.input,
                    focusedField === "password" && styles.inputFocused,
                  ]}
                  placeholder={t("login.passwordPlaceholder")}
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
                  autoComplete="current-password"
                  textContentType="password"
                  returnKeyType="go"
                  onSubmitEditing={handleSignIn}
                  accessibilityLabel={t("login.password")}
                />
              </View>

              <Text style={styles.error} accessibilityLiveRegion="polite">
                {error || initializationError || " "}
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
              <Text style={styles.buttonText}>
                {busy ? t("common.processing") : t("login.signIn")}
              </Text>
            </Pressable>

            <View style={styles.links}>
              {/* Disabled until these features are implemented. */}
              <Pressable disabled style={styles.link}>
                <Text style={styles.linkText}>{t("login.findId")}</Text>
              </Pressable>

              <View style={styles.divider} />

              <Pressable disabled style={styles.link}>
                <Text style={styles.linkText}>{t("login.findPassword")}</Text>
              </Pressable>

              <View style={styles.divider} />

              <Pressable disabled={busy} style={styles.link} accessibilityRole="button" onPress={() => router.push("/signup")}>
                <Text style={styles.linkText}>{t("login.signUp")}</Text>
              </Pressable>
            </View>
            <LanguageSelector variant="row" />
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
