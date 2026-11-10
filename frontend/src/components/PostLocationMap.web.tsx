import { Linking, Pressable, StyleSheet, Text, View } from "react-native";

import GoogleMap from "@/components/GoogleMap.web";
import { Colors, Fonts } from "@/constants/theme";
import { useLocale } from "@/i18n/LocaleProvider";

type Props = {
  latitude: number;
  longitude: number;
};

export default function PostLocationMap({ latitude, longitude }: Props) {
  const { t } = useLocale();
  const mapUrl = `https://www.google.com/maps/search/?api=1&query=${latitude},${longitude}`;
  const location = { latitude, longitude };

  return (
    <View style={styles.container}>
      <GoogleMap center={location} marker={location} style={styles.map} />
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
    alignItems: "center",
    gap: 12,
    borderRadius: 12,
    overflow: "hidden",
    width: "100%",
  },
  map: {
    height: 220,
  },
  button: {
    alignSelf: "flex-start",
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
