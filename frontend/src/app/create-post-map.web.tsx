import { router } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { Colors, Fonts } from "@/constants/theme";
import { useLocale } from "@/i18n/LocaleProvider";

export default function CreatePostMapWeb() {
  const { t } = useLocale();

  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.header}>
        <Pressable
          accessibilityLabel={t("common.back")}
          onPress={() => router.back()}
          style={styles.back}
        >
          <Text style={styles.backText}>‹</Text>
        </Pressable>
        <Text style={styles.title}>{t("map.title")}</Text>
        <View style={styles.back} />
      </View>
      <View style={styles.content}>
        <Text style={styles.message}>{t("map.webUnavailable")}</Text>
        <Pressable
          accessibilityRole="button"
          onPress={() => router.back()}
          style={styles.button}
        >
          <Text style={styles.buttonText}>{t("common.back")}</Text>
        </Pressable>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#FFF" },
  header: {
    height: 64,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 20,
  },
  back: { width: 44, height: 44, justifyContent: "center" },
  backText: { fontSize: 36, color: "#111" },
  title: {
    fontSize: 18,
    color: "#111",
    fontFamily: Fonts.pretendardSemiBold,
  },
  content: {
    flex: 1,
    alignItems: "center",
    justifyContent: "center",
    paddingHorizontal: 28,
  },
  message: {
    color: "#555",
    fontFamily: Fonts.pretendardRegular,
    fontSize: 15,
    lineHeight: 24,
    textAlign: "center",
  },
  button: {
    marginTop: 24,
    minWidth: 160,
    height: 46,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 12,
    backgroundColor: Colors.primary,
  },
  buttonText: {
    color: "#FFF",
    fontFamily: Fonts.pretendardMedium,
    fontSize: 15,
  },
});
