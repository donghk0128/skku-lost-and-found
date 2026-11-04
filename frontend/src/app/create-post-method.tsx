import { useLocalSearchParams, useRouter } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { Fonts } from "@/constants/theme";
import { useLocale } from "@/i18n/LocaleProvider";

export default function CreatePostMethodScreen() {
  const { t } = useLocale();
  const router = useRouter();
  const { type } = useLocalSearchParams<{ type?: string }>();
  const postType = type === "FOUND" ? "FOUND" : "LOST";
  const action =
    postType === "LOST"
      ? t("createMethod.lostQuestion")
      : t("createMethod.foundQuestion");

  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.header}>
        <Pressable accessibilityLabel={t("common.back")} onPress={() => router.back()} style={styles.back}>
          <Text style={styles.backText}>‹</Text>
        </Pressable>
        <Text style={styles.headerTitle}>{t("createMethod.title")}</Text>
        <View style={styles.back} />
      </View>
      <View style={styles.content}>
        <Text style={styles.title}>{action}</Text>
        <Text style={styles.subtitle}>{t("createMethod.prompt")}</Text>
        <View style={styles.options}>
          <Pressable
            accessibilityRole="button"
            onPress={() =>
              router.push({
                pathname: "/create-post-ai",
                params: { type: postType },
              } as never)
            }
            style={styles.aiOption}
          >
            <Text style={styles.aiTitle}>{t("createMethod.aiTitle")}</Text>
            <Text style={styles.aiHint}>{t("createMethod.aiHint")}</Text>
          </Pressable>
          <Pressable
            accessibilityRole="button"
            onPress={() => router.push({ pathname: "/create-post", params: { type: postType } })}
            style={styles.manualOption}
          >
            <Text style={styles.manualTitle}>{t("createMethod.manualTitle")}</Text>
            <Text style={styles.manualHint}>{t("createMethod.manualHint")}</Text>
          </Pressable>
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "white" },
  header: { height: 64, flexDirection: "row", alignItems: "center", justifyContent: "space-between", paddingHorizontal: 18 },
  back: { width: 44, height: 44, justifyContent: "center" },
  backText: { fontSize: 34, color: "#111" },
  headerTitle: { color: "#111", fontFamily: Fonts.pretendardSemiBold, fontSize: 17 },
  content: { flex: 1, paddingHorizontal: 28, paddingTop: 34 },
  title: { color: "#111", fontFamily: Fonts.pretendardSemiBold, fontSize: 24 },
  subtitle: { color: "#999", fontFamily: Fonts.pretendardRegular, fontSize: 13, marginTop: 10 },
  options: { gap: 14, marginTop: 128 },
  aiOption: { borderColor: "#4A82FF", borderRadius: 12, borderWidth: 1, minHeight: 76, justifyContent: "center", paddingHorizontal: 16 },
  manualOption: { borderColor: "#333", borderRadius: 12, borderWidth: 1, minHeight: 76, justifyContent: "center", paddingHorizontal: 16 },
  aiTitle: { color: "#3173FF", fontFamily: Fonts.pretendardSemiBold, fontSize: 15 },
  manualTitle: { color: "#111", fontFamily: Fonts.pretendardSemiBold, fontSize: 15 },
  aiHint: { color: "#7199EB", fontFamily: Fonts.pretendardRegular, fontSize: 12, marginTop: 6 },
  manualHint: { color: "#999", fontFamily: Fonts.pretendardRegular, fontSize: 12, marginTop: 6 },
});
