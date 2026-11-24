import type { ReactNode } from "react";
import { useRouter } from "expo-router";
import {
  KeyboardAvoidingView, Platform, Pressable, ScrollView, StyleSheet,
  Text, TextInput, View, type TextInputProps,
} from "react-native";
import { useSafeAreaInsets } from "react-native-safe-area-context";
import { Colors, Fonts, MaxContentWidth } from "@/constants/theme";
import ChevronLeftIcon from "@/assets/icons/chevron-left.svg";
import { tabHeaderStyles } from "@/components/tab-header-styles";
import { useLocale } from "@/i18n/LocaleProvider";

export function AccountScreen({ title, children, footer, busy = false, tab = false, scroll = true }: {
  title: string; children: ReactNode; footer?: ReactNode; busy?: boolean; tab?: boolean; scroll?: boolean;
}) {
  const router = useRouter();
  const { t } = useLocale();
  const insets = useSafeAreaInsets();
  return (
    <KeyboardAvoidingView style={s.root} behavior={Platform.OS === "ios" ? "padding" : "height"}>
      <View style={{ paddingTop: insets.top }}>
        {tab ? (
          <View style={{ paddingLeft: insets.left, paddingRight: insets.right }}>
            <View style={tabHeaderStyles.container}>
              <View style={tabHeaderStyles.row}>
                <Text accessibilityRole="header" style={s.tabTitle}>{title}</Text>
              </View>
            </View>
          </View>
        ) : (
          <View style={[s.header, { paddingLeft: insets.left + 18, paddingRight: insets.right + 18 }]}>
            <Pressable
              accessibilityRole="button"
              accessibilityLabel={t("common.back")}
              disabled={busy}
              style={s.back}
              onPress={() => router.canGoBack() ? router.back() : router.replace("/(tabs)/account")}
            >
              <ChevronLeftIcon width={24} height={24} color="#000000" />
            </Pressable>
            <Text accessibilityRole="header" numberOfLines={1} style={s.headerTitle}>{title}</Text>
            <View style={s.back} />
          </View>
        )}
      </View>
      {scroll
        ? <ScrollView keyboardShouldPersistTaps="handled" contentContainerStyle={[s.content, tab && s.tabContent, { paddingBottom: tab ? 120 : 28 }]}>{children}</ScrollView>
        : <View style={[s.content, { flex: 1, minHeight: 0, paddingBottom: 0 }]}>{children}</View>}
      {footer ? <View style={[s.footer, { paddingBottom: Math.max(insets.bottom, 16) }]}>{footer}</View> : null}
    </KeyboardAvoidingView>
  );
}

export function AccountButton({ label, onPress, disabled = false, secondary = false, danger = false }: {
  label: string; onPress: () => void; disabled?: boolean; secondary?: boolean; danger?: boolean;
}) {
  return <Pressable accessibilityRole="button" accessibilityState={{ disabled }} disabled={disabled} onPress={onPress}
    style={[s.button, secondary && s.secondary, danger && { backgroundColor: "#B13B3B" }, disabled && { opacity: 0.45 }]}>
    <Text style={[s.buttonText, secondary && { color: "#34463F" }]}>{label}</Text>
  </Pressable>;
}

export function AccountField({ label, ...props }: TextInputProps & { label: string }) {
  return <View style={s.field}>
    <Text style={s.label}>{label}</Text>
    <TextInput accessibilityLabel={label} placeholderTextColor="#929B97" autoCapitalize="none" autoCorrect={false}
      {...props} style={[s.input, props.style]} />
  </View>;
}

export function AccountError({ message }: { message: string }) {
  return message ? <Text accessibilityRole="alert" style={s.error}>{message}</Text> : null;
}

export const accountStyles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#FFFFFF" },
  header: { minHeight: 64, flexDirection: "row", alignItems: "center", gap: 8 },
  back: { width: 44, height: 44, justifyContent: "center" },
  headerTitle: { flex: 1, textAlign: "center", fontSize: 17, fontFamily: Fonts.pretendardSemiBold, color: "#111" },
  tabTitle: { fontSize: 28, lineHeight: 32, fontFamily: Fonts.pretendardSemiBold, color: "#111" },
  content: { padding: 24, paddingTop: 16, gap: 20, width: "100%", maxWidth: 680, alignSelf: "center" },
  tabContent: { maxWidth: MaxContentWidth, paddingTop: 28 },
  footer: { borderTopWidth: 1, borderColor: "#E8EDE9", padding: 20, gap: 10, width: "100%", maxWidth: 680, alignSelf: "center", backgroundColor: "#FFFFFF" },
  button: { minHeight: 52, padding: 14, borderRadius: 14, backgroundColor: Colors.primary, alignItems: "center", justifyContent: "center" },
  secondary: { backgroundColor: "#EDF3EF" },
  buttonText: { color: "#FFFFFF", fontSize: 16, fontFamily: Fonts.pretendardSemiBold },
  field: { gap: 10 },
  label: { fontSize: 15, fontFamily: Fonts.pretendardSemiBold, color: "#34463F" },
  input: { minHeight: 54, borderWidth: 1, borderColor: "#DDE5E0", borderRadius: 14, padding: 16, fontSize: 16, color: "#20372B", fontFamily: Fonts.pretendardRegular },
  copy: { fontSize: 15, lineHeight: 24, color: "#66736B", fontFamily: Fonts.pretendardRegular },
  error: { color: "#B33333", fontSize: 14, lineHeight: 22 },
  card: { backgroundColor: "#F3F7F4", padding: 20, borderRadius: 18, gap: 12 },
  row: { minHeight: 64, borderBottomWidth: 1, borderColor: "#E8EDE9", flexDirection: "row", alignItems: "center", justifyContent: "space-between", gap: 12 },
  rowLabel: { flex: 1, fontSize: 16, fontFamily: Fonts.pretendardMedium, color: "#34463F" },
  placeholder: { color: "#87928C", fontSize: 13, backgroundColor: "#F0F3F1", paddingHorizontal: 10, paddingVertical: 5, borderRadius: 8 },
});
const s = accountStyles;
