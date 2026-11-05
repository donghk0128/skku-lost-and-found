import { useLocalSearchParams, useRouter } from "expo-router";
import {
  ImageBackground,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
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
        <Pressable
          accessibilityLabel={t("common.back")}
          onPress={() => router.back()}
          style={styles.back}
        >
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
            style={({ pressed }) => [
              styles.option,
              styles.aiOption,
              pressed && styles.pressed,
            ]}
          >
            <ImageBackground
              source={require("@/assets/images/ai-create-post-bg.png")}
              resizeMode="cover"
              blurRadius={8}
              style={styles.aiArtwork}
            >
              <View style={styles.aiContent}>
                <Text style={styles.aiTitle}>{t("createMethod.aiTitle")}</Text>
                <Text style={styles.aiHint}>{t("createMethod.aiHint")}</Text>
                <View style={styles.aiButton}>
                  <Text style={styles.aiButtonText}>
                    {t("createMethod.goTo")} <Text style={styles.arrow}>→</Text>
                  </Text>
                </View>
              </View>
            </ImageBackground>
          </Pressable>
          <Pressable
            accessibilityRole="button"
            onPress={() =>
              router.push({
                pathname: "/create-post",
                params: { type: postType },
              })
            }
            style={({ pressed }) => [
              styles.option,
              styles.manualOption,
              pressed && styles.pressed,
            ]}
          >
            <Text style={styles.manualTitle}>
              {t("createMethod.manualTitle")}
            </Text>
            <Text style={styles.manualHint}>
              {t("createMethod.manualHint")}
            </Text>
            <View style={styles.manualButton}>
              <Text style={styles.manualButtonText}>
                {t("createMethod.goTo")} <Text style={styles.arrow}>→</Text>
              </Text>
            </View>
          </Pressable>
        </View>
      </View>
    </SafeAreaView>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "white" },
  header: {
    height: 64,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 18,
  },
  back: { width: 44, height: 44, justifyContent: "center" },
  backText: { fontSize: 34, color: "#111" },
  headerTitle: {
    color: "#111",
    fontFamily: Fonts.pretendardSemiBold,
    fontSize: 17,
  },
  content: {
    flex: 1,
    paddingHorizontal: 24,
    paddingTop: 20,
    paddingBottom: 20,
  },
  title: { color: "#111", fontFamily: Fonts.pretendardSemiBold, fontSize: 24 },
  subtitle: {
    color: "#888",
    fontFamily: Fonts.pretendardRegular,
    fontSize: 14,
    marginTop: 10,
  },
  options: { gap: 24, marginTop: 28 },
  option: {
    borderRadius: 22,
    minHeight: 190,
    aspectRatio: 1.65,
    overflow: "hidden",
    shadowColor: "#000",
    shadowOffset: { width: 0, height: 5 },
    shadowOpacity: 0.18,
    shadowRadius: 6,
    elevation: 5,
  },
  pressed: { opacity: 0.9, transform: [{ scale: 0.99 }] },
  aiOption: { backgroundColor: "#061810", justifyContent: "center" },
  aiArtwork: {
    flex: 1,
    justifyContent: "center",
  },
  aiContent: {
    alignItems: "flex-start",
    paddingHorizontal: 28,
    paddingVertical: 20,
  },
  aiTitle: { color: "#FFF", fontFamily: Fonts.pretendardBold, fontSize: 20 },
  aiHint: {
    color: "#D0D7D3",
    fontFamily: Fonts.pretendardRegular,
    fontSize: 14,
    lineHeight: 22,
    marginTop: 14,
  },
  aiButton: {
    backgroundColor: "#FFF",
    borderRadius: 999,
    marginTop: 20,
    paddingHorizontal: 18,
    paddingVertical: 11,
  },
  aiButtonText: {
    color: "#111",
    fontFamily: Fonts.pretendardSemiBold,
    fontSize: 16,
  },
  arrow: { fontFamily: Fonts.pretendardMedium },
  manualOption: {
    backgroundColor: "#F2F2F2",
    borderColor: "#B5B5B5",
    borderWidth: 1,
    justifyContent: "center",
    paddingHorizontal: 28,
    paddingVertical: 20,
  },
  manualTitle: {
    color: "#111",
    fontFamily: Fonts.pretendardBold,
    fontSize: 20,
  },
  manualHint: {
    color: "#929292",
    fontFamily: Fonts.pretendardMedium,
    fontSize: 14,
    lineHeight: 22,
    marginTop: 14,
  },
  manualButton: {
    alignSelf: "flex-start",
    backgroundColor: "#FFF",
    borderRadius: 999,
    marginTop: 20,
    paddingHorizontal: 18,
    paddingVertical: 11,
  },
  manualButtonText: {
    color: "#111",
    fontFamily: Fonts.pretendardMedium,
    fontSize: 16,
  },
});
