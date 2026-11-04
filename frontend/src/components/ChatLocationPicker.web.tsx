import { Linking, Pressable, StyleSheet, Text, View } from "react-native";

import { Colors, Fonts } from "@/constants/theme";
import { useLocale } from "@/i18n/LocaleProvider";

type Props = {
  disabled: boolean;
  locationText: string;
  onConfirm: (location: { address: string; latitude: number; longitude: number }) => void;
};

export default function ChatLocationPicker({
  disabled,
  locationText,
}: Props) {
  const { t } = useLocale();
  const url = `https://www.google.com/maps/search/?api=1&query=${encodeURIComponent(locationText)}`;

  return (
    <View style={styles.card}>
      <Text style={styles.title}>{t("ai.pinLocationPrompt")}</Text>
      <Text style={styles.message}>{t("map.webUnavailable")}</Text>
      <Pressable
        accessibilityRole="link"
        disabled={disabled}
        onPress={() => void Linking.openURL(url)}
        style={styles.button}
      >
        <Text style={styles.buttonText}>{t("map.openInGoogleMaps")}</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  card: {
    alignSelf: "flex-start",
    backgroundColor: "#F4F7F6",
    borderRadius: 16,
    gap: 10,
    maxWidth: "92%",
    padding: 14,
    width: 340,
  },
  title: {
    color: "#333",
    fontFamily: Fonts.pretendardMedium,
    fontSize: 13,
  },
  message: {
    color: "#666",
    fontFamily: Fonts.pretendardRegular,
    fontSize: 12,
    lineHeight: 18,
  },
  button: {
    alignItems: "center",
    backgroundColor: Colors.primary,
    borderRadius: 10,
    paddingVertical: 11,
  },
  buttonText: {
    color: "white",
    fontFamily: Fonts.pretendardMedium,
    fontSize: 13,
  },
});
