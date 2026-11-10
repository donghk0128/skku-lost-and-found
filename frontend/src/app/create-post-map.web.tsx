import { useEffect, useMemo, useRef, useState } from "react";
import { router, useLocalSearchParams } from "expo-router";
import {
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";

import GoogleMap from "@/components/GoogleMap.web";
import { Colors, Fonts } from "@/constants/theme";
import { useLocale } from "@/i18n/LocaleProvider";
import { pickLocation } from "@/lib/location-picker";
import {
  reverseGeocode,
  type MapCoordinates,
} from "@/lib/google-maps.web";

const CAMPUSES = {
  humanities: { latitude: 37.5882, longitude: 126.9933 },
  science: { latitude: 37.2939, longitude: 126.9751 },
};

export default function CreatePostMapWeb() {
  const { locale, t } = useLocale();
  const { latitude, longitude } = useLocalSearchParams<{
    latitude?: string;
    longitude?: string;
  }>();
  const initialPin = useMemo(() => {
    if (!latitude || !longitude) return null;
    const parsedLatitude = Number(latitude);
    const parsedLongitude = Number(longitude);
    if (
      !Number.isFinite(parsedLatitude) ||
      !Number.isFinite(parsedLongitude) ||
      parsedLatitude < -90 ||
      parsedLatitude > 90 ||
      parsedLongitude < -180 ||
      parsedLongitude > 180
    ) {
      return null;
    }
    return { latitude: parsedLatitude, longitude: parsedLongitude };
  }, [latitude, longitude]);
  const [pin, setPin] = useState<MapCoordinates | null>(initialPin);
  const [center, setCenter] = useState<MapCoordinates>(
    initialPin ?? CAMPUSES.science,
  );
  const [placeName, setPlaceName] = useState("");
  const [addressLoading, setAddressLoading] = useState(false);
  const [locationError, setLocationError] = useState("");
  const addressRequest = useRef(0);

  useEffect(() => {
    if (!pin) {
      setPlaceName("");
      setAddressLoading(false);
      return;
    }

    let active = true;
    const requestId = ++addressRequest.current;
    setPlaceName("");
    setAddressLoading(true);
    reverseGeocode(pin, locale)
      .then((address) => {
        if (active) setPlaceName(address);
      })
      .catch(() => {
        if (active) setPlaceName(t("map.addressLoadFailed"));
      })
      .finally(() => {
        if (active && requestId === addressRequest.current) {
          setAddressLoading(false);
        }
      });
    return () => {
      active = false;
    };
  }, [locale, pin, t]);

  const goToCurrentLocation = () => {
    setLocationError("");
    if (!navigator.geolocation) {
      setLocationError(t("map.currentLocationFailed"));
      return;
    }
    navigator.geolocation.getCurrentPosition(
      ({ coords }) => {
        const current = {
          latitude: coords.latitude,
          longitude: coords.longitude,
        };
        setPin(current);
        setCenter(current);
      },
      () => setLocationError(t("map.currentLocationFailed")),
      { enableHighAccuracy: true, timeout: 10000 },
    );
  };

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
        <Text style={styles.title}>{t("map.title")}</Text>
        <View style={styles.back} />
      </View>
      <View style={styles.content}>
        <GoogleMap
          center={center}
          marker={pin}
          interactive
          onMapPress={(coordinates) => {
            setPin(coordinates);
            setLocationError("");
          }}
          style={styles.map}
        />
        <View pointerEvents="box-none" style={styles.chips}>
          <Chip
            label={t("map.currentLocation")}
            primary
            onPress={goToCurrentLocation}
          />
          <Chip
            label={t("map.humanitiesCampus")}
            onPress={() => setCenter(CAMPUSES.humanities)}
          />
          <Chip
            label={t("map.scienceCampus")}
            onPress={() => setCenter(CAMPUSES.science)}
          />
        </View>
        <View style={styles.selection}>
          <Text
            numberOfLines={2}
            style={[styles.message, pin ? styles.selectedAddress : null]}
          >
            {!pin
              ? t("map.tapToChoose")
              : addressLoading
                ? t("map.loadingAddress")
                : placeName || t("map.addressLoadFailed")}
          </Text>
          {locationError ? (
            <Text accessibilityRole="alert" style={styles.locationError}>
              {locationError}
            </Text>
          ) : null}
          <Pressable
            accessibilityRole="button"
            disabled={
              !pin ||
              !placeName ||
              placeName === t("map.addressLoadFailed") ||
              addressLoading
            }
            onPress={() => {
              if (!pin || !placeName || placeName === t("map.addressLoadFailed")) {
                return;
              }
              pickLocation({ address: placeName, ...pin });
              router.back();
            }}
            style={[
              styles.button,
              (!pin ||
                !placeName ||
                placeName === t("map.addressLoadFailed") ||
                addressLoading) &&
                styles.buttonDisabled,
            ]}
          >
            <Text style={styles.buttonText}>{t("map.selectLocation")}</Text>
          </Pressable>
        </View>
      </View>
    </SafeAreaView>
  );
}

function Chip({
  label,
  onPress,
  primary,
}: {
  label: string;
  onPress: () => void;
  primary?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      style={[styles.chip, primary && styles.primaryChip]}
    >
      <Text style={[styles.chipText, primary && styles.primaryChipText]}>
        {label}
      </Text>
    </Pressable>
  );
}

const styles = StyleSheet.create({
  root: { flex: 1, backgroundColor: "#FFF" },
  header: {
    height: 64,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
    paddingHorizontal: 20,
  },
  back: { width: 44, height: 44, justifyContent: "center" },
  backText: { fontSize: 36, color: "#111" },
  title: {
    fontSize: 18,
    color: "#111",
    fontFamily: Fonts.pretendardSemiBold,
  },
  content: {
    flex: 1,
    position: "relative",
  },
  map: {
    flex: 1,
  },
  chips: {
    position: "absolute",
    top: 12,
    left: 16,
    right: 16,
    flexDirection: "row",
    flexWrap: "wrap",
    gap: 8,
  },
  chip: {
    paddingHorizontal: 12,
    paddingVertical: 8,
    borderRadius: 999,
    backgroundColor: "#FFF",
    elevation: 4,
  },
  primaryChip: { backgroundColor: Colors.primary },
  chipText: {
    fontSize: 13,
    color: "#111",
    fontFamily: Fonts.pretendardMedium,
  },
  primaryChipText: { color: "#FFF" },
  selection: {
    position: "absolute",
    left: 16,
    right: 16,
    bottom: 16,
    padding: 18,
    borderRadius: 20,
    backgroundColor: "#FFF",
    elevation: 8,
  },
  message: {
    color: "#555",
    fontFamily: Fonts.pretendardRegular,
    fontSize: 15,
    lineHeight: 24,
  },
  selectedAddress: {
    color: "#111",
    fontFamily: Fonts.pretendardSemiBold,
  },
  locationError: {
    marginTop: 6,
    color: "#B42318",
    fontFamily: Fonts.pretendardRegular,
    fontSize: 13,
  },
  button: {
    marginTop: 24,
    minWidth: 160,
    height: 46,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 12,
    backgroundColor: Colors.primary,
  },
  buttonDisabled: { opacity: 0.4 },
  buttonText: {
    color: "#FFF",
    fontFamily: Fonts.pretendardMedium,
    fontSize: 15,
  },
});
