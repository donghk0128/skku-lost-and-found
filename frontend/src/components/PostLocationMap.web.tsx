import { Linking, Pressable, StyleSheet, Text, View } from "react-native";

import { Colors, Fonts } from "@/constants/theme";
import { useLocale } from "@/i18n/LocaleProvider";

type Props = {
  latitude: number;
  longitude: number;
};

export default function PostLocationMap({ latitude, longitude }: Props) {
  const { t } = useLocale();
  const mapUrl = `https://www.google.com/maps/search/?api=1&query=${latitude},${longitude}`;

  return (
    <View style={styles.container}>
      <Text style={styles.message}>{t("map.webUnavailable")}</Text>
      <Pressable
        accessibilityRole="link"
        onPress={() => void Linking.openURL(mapUrl)}
        style={styles.button}
      >
        <Text style={styles.buttonText}>{t("map.openInGoogleMaps")}</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    minHeight: 120,
    alignItems: "center",
    justifyContent: "center",
    padding: 16,
    borderRadius: 12,
    backgroundColor: "#F5F7FA",
  },
  message: {
    color: "#555",
    fontFamily: Fonts.pretendardRegular,
    fontSize: 14,
    textAlign: "center",
  },
  button: {
    marginTop: 12,
    paddingHorizontal: 16,
    paddingVertical: 10,
    borderRadius: 10,
    backgroundColor: Colors.primary,
  },
  buttonText: {
    color: "#FFF",
    fontFamily: Fonts.pretendardMedium,
    fontSize: 14,
  },
});
