import { useRef, useState } from "react";
import {
  Modal,
  Pressable,
  StyleSheet,
  Text,
  useWindowDimensions,
  View,
} from "react-native";
import Svg, { Circle, Ellipse, Path } from "react-native-svg";
import { Fonts } from "@/constants/theme";
import type { Locale } from "@/i18n";
import { useLocale } from "@/i18n/LocaleProvider";

type Props = {
  variant?: "icon" | "row";
};

const menuWidth = 210;
const menuHeight = 190;

export default function LanguageSelector({ variant = "icon" }: Props) {
  const triggerRef = useRef<View>(null);
  const { height, width } = useWindowDimensions();
  const { locale, setLocale, t } = useLocale();
  const [visible, setVisible] = useState(false);
  const [position, setPosition] = useState({ left: 0, top: 0 });
  const [saveError, setSaveError] = useState("");

  const open = () => {
    setSaveError("");
    triggerRef.current?.measureInWindow((x, y, triggerWidth, triggerHeight) => {
      const desiredLeft =
        variant === "icon"
          ? x + triggerWidth - menuWidth
          : x + triggerWidth / 2 - menuWidth / 2;
      const desiredTop = y + triggerHeight + 8;
      setPosition({
        left: Math.max(12, Math.min(desiredLeft, width - menuWidth - 12)),
        top:
          desiredTop + menuHeight <= height - 12
            ? desiredTop
            : Math.max(12, y - menuHeight - 8),
      });
      setVisible(true);
    });
  };

  const choose = async (nextLocale: Locale) => {
    try {
      await setLocale(nextLocale);
      setVisible(false);
    } catch (error) {
      setSaveError(
        `${t("language.saveFailed")} ${
          error instanceof Error ? error.message : ""
        }`.trim(),
      );
    }
  };

  return (
    <>
      <Pressable
        ref={triggerRef}
        accessibilityRole="button"
        accessibilityLabel={t("language.change")}
        onPress={open}
        style={({ pressed }) => [
          variant === "icon" ? styles.iconTrigger : styles.rowTrigger,
          pressed && styles.pressed,
        ]}
      >
        <Svg width={22} height={22} viewBox="0 0 24 24" fill="none">
          <Circle cx={12} cy={12} r={9} stroke="#30353A" strokeWidth={1.6} />
          <Ellipse
            cx={12}
            cy={12}
            rx={4}
            ry={9}
            stroke="#30353A"
            strokeWidth={1.4}
          />
          <Path d="M3.5 9h17M3.5 15h17" stroke="#30353A" strokeWidth={1.4} />
        </Svg>
        {variant === "row" ? (
          <Text style={styles.rowLabel}>{t("language.change")}</Text>
        ) : null}
      </Pressable>

      <Modal
        visible={visible}
        transparent
        animationType="fade"
        statusBarTranslucent
        onRequestClose={() => setVisible(false)}
      >
        <View style={styles.overlay}>
          <Pressable
            style={StyleSheet.absoluteFill}
            accessibilityRole="button"
            accessibilityLabel={t("common.close")}
            onPress={() => setVisible(false)}
          />
          <View
            accessibilityViewIsModal
            style={[styles.popover, position]}
          >
            <Text style={styles.title}>{t("language.title")}</Text>
            <Pressable
              accessibilityRole="button"
              accessibilityState={{ selected: locale === "ko" }}
              onPress={() => void choose("ko")}
              style={styles.option}
            >
              <Text style={styles.optionText}>{t("language.korean")}</Text>
              <Text style={styles.check}>{locale === "ko" ? "✓" : ""}</Text>
            </Pressable>
            <Pressable
              accessibilityRole="button"
              accessibilityState={{ selected: locale === "en" }}
              onPress={() => void choose("en")}
              style={styles.option}
            >
              <Text style={styles.optionText}>{t("language.english")}</Text>
              <Text style={styles.check}>{locale === "en" ? "✓" : ""}</Text>
            </Pressable>
            {saveError ? (
              <Text accessibilityRole="alert" style={styles.saveError}>
                {saveError}
              </Text>
            ) : null}
          </View>
        </View>
      </Modal>
    </>
  );
}

const styles = StyleSheet.create({
  overlay: { flex: 1 },
  iconTrigger: {
    width: 44,
    height: 44,
    alignItems: "center",
    justifyContent: "center",
  },
  rowTrigger: {
    minHeight: 44,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "center",
    gap: 8,
    paddingHorizontal: 12,
  },
  rowLabel: {
    color: "#777B81",
    fontSize: 13,
    fontFamily: Fonts.pretendardMedium,
  },
  pressed: { opacity: 0.65 },
  popover: {
    position: "absolute",
    width: menuWidth,
    padding: 12,
    borderRadius: 14,
    backgroundColor: "#FFFFFF",
    borderWidth: 1,
    borderColor: "#E6E7E8",
    shadowColor: "#000000",
    shadowOffset: { width: 0, height: 5 },
    shadowOpacity: 0.14,
    shadowRadius: 14,
    elevation: 8,
  },
  title: {
    paddingHorizontal: 10,
    paddingVertical: 8,
    color: "#777B81",
    fontSize: 12,
    fontFamily: Fonts.pretendardMedium,
  },
  option: {
    minHeight: 44,
    paddingHorizontal: 10,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    borderRadius: 8,
  },
  optionText: {
    color: "#222222",
    fontSize: 14,
    fontFamily: Fonts.pretendardMedium,
  },
  check: {
    minWidth: 20,
    color: "#00785D",
    fontSize: 16,
    textAlign: "right",
  },
  saveError: {
    paddingHorizontal: 10,
    paddingTop: 6,
    color: "#B54747",
    fontSize: 11,
    lineHeight: 16,
    fontFamily: Fonts.pretendardRegular,
  },
});
