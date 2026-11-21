import { useEffect } from "react";
import { StyleSheet, Text, View } from "react-native";
import Animated, {
  cancelAnimation,
  Easing,
  useAnimatedStyle,
  useReducedMotion,
  useSharedValue,
  withRepeat,
  withTiming,
  type SharedValue,
} from "react-native-reanimated";
import { Fonts } from "@/constants/theme";

function ShimmerLetter({ letter, index, count, progress }: {
  letter: string;
  index: number;
  count: number;
  progress: SharedValue<number>;
}) {
  const animatedStyle = useAnimatedStyle(() => {
    const distance = Math.abs(progress.value * (count + 8) - index - 4);
    return { opacity: 1 - Math.max(0, 1 - distance / 4) * 0.65 };
  });
  return <Animated.Text style={[styles.text, animatedStyle]}>{letter}</Animated.Text>;
}

export default function ChatThinkingText({ text }: { text: string }) {
  const progress = useSharedValue(0);
  const reducedMotion = useReducedMotion();
  useEffect(() => {
    if (reducedMotion) return;
    progress.value = withRepeat(withTiming(1, {
      duration: 2200,
      easing: Easing.linear,
    }), -1, false);
    return () => cancelAnimation(progress);
  }, [progress, reducedMotion]);
  const letters = Array.from(text);
  return (
    <View style={styles.row} accessible accessibilityLabel={text} accessibilityRole="text" accessibilityLiveRegion="polite">
      {reducedMotion ? <Text style={styles.text}>{text}</Text> : letters.map((letter, index) => (
        <ShimmerLetter key={index} letter={letter} index={index} count={letters.length} progress={progress} />
      ))}
    </View>
  );
}

const styles = StyleSheet.create({
  row: { flexDirection: "row", alignSelf: "flex-start", paddingVertical: 10 },
  text: { color: "#888888", fontSize: 14, lineHeight: 21, fontFamily: Fonts.pretendardRegular },
});
