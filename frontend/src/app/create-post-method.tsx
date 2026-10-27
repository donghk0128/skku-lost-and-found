import { useLocalSearchParams, useRouter } from "expo-router";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import { Fonts } from "@/constants/theme";

export default function CreatePostMethodScreen() {
  const router = useRouter();
  const { type } = useLocalSearchParams<{ type?: string }>();
  const postType = type === "FOUND" ? "FOUND" : "LOST";
  const action = postType === "LOST" ? "잃어버리셨나요?" : "주우셨나요?";

  return (
    <SafeAreaView style={styles.root}>
      <View style={styles.header}>
        <Pressable accessibilityLabel="뒤로가기" onPress={() => router.back()} style={styles.back}>
          <Text style={styles.backText}>‹</Text>
        </Pressable>
        <Text style={styles.headerTitle}>게시글 작성</Text>
        <View style={styles.back} />
      </View>
      <View style={styles.content}>
        <Text style={styles.title}>무엇을 {action}</Text>
        <Text style={styles.subtitle}>게시글을 작성할 방식을 찾아보세요</Text>
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
            <Text style={styles.aiTitle}>AI와 함께 작성하기</Text>
            <Text style={styles.aiHint}>AI의 질문에 답하며 글을 간편하게 써보세요</Text>
          </Pressable>
          <Pressable
            accessibilityRole="button"
            onPress={() => router.push({ pathname: "/create-post", params: { type: postType } })}
            style={styles.manualOption}
          >
            <Text style={styles.manualTitle}>혼자 작성하기</Text>
            <Text style={styles.manualHint}>직접 게시물을 작성하세요</Text>
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
