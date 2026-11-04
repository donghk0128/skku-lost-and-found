import axios from "axios";
import MapView, { Marker, PROVIDER_GOOGLE } from "react-native-maps";
import { useEffect, useRef, useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { Colors, Fonts } from "@/constants/theme";
import type { PickedLocation } from "@/lib/location-picker";
import { useLocale } from "@/i18n/LocaleProvider";

const googleMapsApiKey = process.env.EXPO_PUBLIC_GOOGLE_MAPS_API_KEY;
const INITIAL_REGION = {
  latitude: 37.2939,
  longitude: 126.9751,
  latitudeDelta: 0.02,
  longitudeDelta: 0.02,
};

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
  const mapRef = useRef<MapView>(null);
  const [pin, setPin] = useState<PickedLocation | null>(null);
  const [address, setAddress] = useState("");
  const [confirmed, setConfirmed] = useState(false);

  useEffect(() => {
    if (!pin) return;
    let active = true;
    const url = new URL("https://maps.googleapis.com/maps/api/geocode/json");
    url.searchParams.set("latlng", `${pin.latitude},${pin.longitude}`);
    url.searchParams.set("language", locale);
    if (googleMapsApiKey) url.searchParams.set("key", googleMapsApiKey);

    axios
      .get<{ results: { formatted_address: string }[]; status: string }>(url.toString())
      .then((response) => {
        if (!active) return;
        setAddress(
          response.data.results[0]?.formatted_address ?? t("map.unknownAddress"),
        );
      })
      .catch(() => {
        if (active) setAddress(t("map.addressLoadFailed"));
      });

    return () => {
      active = false;
    };
  }, [locale, pin, t]);

  return (
    <View style={styles.card}>
      <Text style={styles.title}>{t("ai.pinLocationPrompt")}</Text>
      <MapView
        ref={mapRef}
        provider={PROVIDER_GOOGLE}
        style={styles.map}
        initialRegion={INITIAL_REGION}
        onPress={(event) => {
          if (disabled) return;
          const { latitude, longitude } = event.nativeEvent.coordinate;
          setPin({ address: "", latitude, longitude });
          setAddress("");
          setConfirmed(false);
        }}
        scrollEnabled={!disabled}
        zoomEnabled={!disabled}
      >
        {pin ? (
          <Marker coordinate={pin} pinColor={Colors.primary} />
        ) : null}
      </MapView>
      <Text style={styles.address} numberOfLines={2}>
        {pin ? address || t("map.loadingAddress") : t("map.tapToChoose")}
      </Text>
      <Pressable
        accessibilityRole="button"
        disabled={disabled || !pin || !address || address === t("map.addressLoadFailed")}
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
          (disabled || !pin || !address || address === t("map.addressLoadFailed")) &&
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
    padding: 12,
    width: 340,
  },
  title: {
    color: "#333",
    fontFamily: Fonts.pretendardMedium,
    fontSize: 13,
  },
  map: {
    height: 210,
    width: "100%",
  },
  address: {
    color: "#666",
    fontFamily: Fonts.pretendardRegular,
    fontSize: 12,
    minHeight: 18,
  },
  button: {
    alignItems: "center",
    backgroundColor: Colors.primary,
    borderRadius: 10,
    paddingVertical: 11,
  },
  buttonDisabled: {
    opacity: 0.45,
  },
  buttonText: {
    color: "white",
    fontFamily: Fonts.pretendardMedium,
    fontSize: 13,
  },
});
