import { useRef, useState } from "react";
import { Animated, Modal, Pressable, StyleSheet, Text, useWindowDimensions, View } from "react-native";
import { useRouter } from "expo-router";
import { BottomTabInset, Colors, Fonts } from "@/constants/theme";

export default function CreatePostButton() {
  const router = useRouter();
  const { height, width } = useWindowDimensions();
  const trigger = useRef<View>(null);
  const [anchor, setAnchor] = useState<{ left: number; top: number } | null>(null);
  const [open, setOpen] = useState(false);
  const [progress] = useState(() => new Animated.Value(0));
  const animate = (value: number, done?: () => void) => Animated.timing(progress, { toValue: value, duration: 220, useNativeDriver: true }).start(({ finished }) => { if (finished) done?.(); });
  const close = (type?: "LOST" | "FOUND") => animate(0, () => {
    setOpen(false);
    if (type) router.push({ pathname: "/create-post", params: { type } });
  });
  const show = () => {
    trigger.current?.measureInWindow((left, top) => {
      setAnchor({ left, top });
      setOpen(true);
      animate(1);
    });
  };
  const button = (expanded: boolean) => <Pressable ref={expanded ? undefined : trigger} pointerEvents={!expanded && open ? "none" : "auto"} accessibilityElementsHidden={!expanded && open} importantForAccessibility={!expanded && open ? "no-hide-descendants" : "auto"} accessibilityRole="button" accessibilityLabel={expanded ? "작성 메뉴 닫기" : "게시글 작성"} onPress={() => expanded ? close() : show()} style={[styles.button, expanded && anchor ? { left: anchor.left, top: anchor.top } : { bottom: BottomTabInset + 20, right: 24 }, !expanded && open && { opacity: 0 }]}>
    <Animated.View style={{ transform: [{ rotate: progress.interpolate({ inputRange: [0, 1], outputRange: ["0deg", "45deg"] }) }], width: 28, height: 28, alignItems: "center", justifyContent: "center" }}><View style={styles.horizontal} /><View style={styles.vertical} /></Animated.View>
  </Pressable>;
  return <>{button(false)}<Modal visible={open} transparent animationType="none" onRequestClose={() => close()} statusBarTranslucent>
    <View style={styles.overlay}>
      <Animated.View style={[StyleSheet.absoluteFill, { opacity: progress }]}><Pressable accessibilityLabel="작성 메뉴 닫기" onPress={() => close()} style={styles.dim} /></Animated.View>
      <Animated.View style={[styles.menu, { bottom: anchor ? height - anchor.top + 16 : BottomTabInset + 100, right: anchor ? width - anchor.left - 64 : 24, opacity: progress, transform: [{ translateY: progress.interpolate({ inputRange: [0, 1], outputRange: [12, 0] }) }] }]}>
        <Pressable accessibilityRole="button" onPress={() => close("LOST")} style={styles.choice}><Text style={styles.title}>분실글 작성</Text><Text style={styles.hint}>잃어버린 물건을 찾아보세요</Text></Pressable>
        <View style={styles.divider} />
        <Pressable accessibilityRole="button" onPress={() => close("FOUND")} style={styles.choice}><Text style={styles.title}>습득글 작성</Text><Text style={styles.hint}>주운 물건의 주인을 찾아주세요</Text></Pressable>
      </Animated.View>
      {button(true)}
    </View>
  </Modal></>;
}
const styles = StyleSheet.create({
  overlay: { flex: 1 }, dim: { flex: 1, backgroundColor: "rgba(0,0,0,0.45)" },
  button: { position: "absolute", width: 64, height: 64, borderRadius: 32, backgroundColor: Colors.primary, alignItems: "center", justifyContent: "center" },
  horizontal: { position: "absolute", width: 28, height: 2, backgroundColor: "white" }, vertical: { position: "absolute", width: 2, height: 28, backgroundColor: "white" },
  menu: { position: "absolute", right: 24, width: 255, backgroundColor: "white", borderRadius: 20, padding: 8 },
  choice: { padding: 18, gap: 7 }, title: { fontFamily: Fonts.pretendardSemiBold, fontSize: 17, color: "#111" }, hint: { fontFamily: Fonts.pretendardRegular, fontSize: 13, color: "#777" }, divider: { height: 1, backgroundColor: "#EEE", marginHorizontal: 16 },
});
