import { useEffect, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import GoogleMap from "@/components/GoogleMap.web";
import { Colors, Fonts } from "@/constants/theme";
import { useLocale } from "@/i18n/LocaleProvider";
import type { PickedLocation } from "@/lib/location-picker";
import { reverseGeocode } from "@/lib/google-maps.web";

type Props = {
  disabled: boolean;
  locationText: string;
  onConfirm: (location: PickedLocation) => void;
};

export default function ChatLocationPicker({
  disabled,
  locationText,
  onConfirm,
}: Props) {
  const { locale, t } = useLocale();
  const [pin, setPin] = useState<{
    latitude: number;
    longitude: number;
  } | null>(null);
  const [address, setAddress] = useState("");
  const [addressLoading, setAddressLoading] = useState(false);
  const [confirmed, setConfirmed] = useState(false);

  useEffect(() => {
    if (!pin) return;
    let active = true;
    setAddress("");
    setAddressLoading(true);
    reverseGeocode(pin, locale)
      .then((result) => {
        if (active) setAddress(result);
      })
      .catch(() => {
        if (active) setAddress(t("map.addressLoadFailed"));
      })
      .finally(() => {
        if (active) setAddressLoading(false);
      });
    return () => {
      active = false;
    };
  }, [locale, pin, t]);

  return (
    <View style={styles.card}>
      <Text style={styles.title}>{t("ai.pinLocationPrompt")}</Text>
      <GoogleMap
        center={{ latitude: 37.2939, longitude: 126.9751 }}
        marker={pin}
        interactive={!disabled}
        onMapPress={(coordinates) => {
          setPin(coordinates);
          setAddress("");
          setConfirmed(false);
        }}
        style={styles.map}
      />
      <Text style={styles.message} numberOfLines={2}>
        {!pin
          ? t("map.tapToChoose")
          : addressLoading
            ? t("map.loadingAddress")
            : address || t("map.addressLoadFailed")}
      </Text>
      <Pressable
        accessibilityRole="button"
        disabled={
          disabled ||
          !pin ||
          !address ||
          address === t("map.addressLoadFailed") ||
          addressLoading
        }
        onPress={() => {
          if (!pin || !address) return;
          onConfirm({
            address: locationText.trim() || address,
            latitude: Number(pin.latitude.toFixed(6)),
            longitude: Number(pin.longitude.toFixed(6)),
          });
          setConfirmed(true);
        }}
        style={[
          styles.button,
          (disabled ||
            !pin ||
            !address ||
            address === t("map.addressLoadFailed") ||
            addressLoading) &&
            styles.buttonDisabled,
        ]}
      >
        <Text style={styles.buttonText}>
          {confirmed ? t("ai.locationPinned") : t("ai.confirmPinnedLocation")}
        </Text>
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
  map: {
    height: 210,
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
  buttonDisabled: {
    opacity: 0.45,
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
