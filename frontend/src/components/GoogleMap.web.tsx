import { useEffect, useRef, useState } from "react";
import { StyleSheet, Text, View, type StyleProp, type ViewStyle } from "react-native";

import { useLocale } from "@/i18n/LocaleProvider";
import {
  GoogleMapsLoadError,
  loadGoogleMaps,
  type GoogleMapInstance,
  type GoogleMapMarker,
  type MapCoordinates,
} from "@/lib/google-maps.web";

type Props = {
  center: MapCoordinates;
  marker?: MapCoordinates | null;
  interactive?: boolean;
  onMapPress?: (coordinates: MapCoordinates) => void;
  style?: StyleProp<ViewStyle>;
};

export default function GoogleMap({
  center,
  marker = null,
  interactive = false,
  onMapPress,
  style,
}: Props) {
  const { locale, t } = useLocale();
  const elementRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<GoogleMapInstance | null>(null);
  const markerRef = useRef<GoogleMapMarker | null>(null);
  const centerRef = useRef(center);
  const markerPositionRef = useRef(marker);
  const onMapPressRef = useRef(onMapPress);
  const interactiveRef = useRef(interactive);
  const [loadError, setLoadError] = useState<"missing-key" | "load-failed" | null>(
    null,
  );

  useEffect(() => {
    centerRef.current = center;
    markerPositionRef.current = marker;
    onMapPressRef.current = onMapPress;
    interactiveRef.current = interactive;
  }, [center, interactive, marker, onMapPress]);

  useEffect(() => {
    let active = true;
    let clickListener: { remove: () => void } | undefined;
    let currentMarker: GoogleMapMarker | null = null;

    loadGoogleMaps(locale)
      .then((google) => {
        if (!active || !elementRef.current) return;
        const map = new google.maps.Map(elementRef.current, {
          center: {
            lat: centerRef.current.latitude,
            lng: centerRef.current.longitude,
          },
          zoom: 16,
          mapTypeControl: false,
          fullscreenControl: false,
          streetViewControl: false,
          clickableIcons: false,
        });
        mapRef.current = map;
        currentMarker = new google.maps.Marker({
          map,
          position: markerPositionRef.current
            ? {
                lat: markerPositionRef.current.latitude,
                lng: markerPositionRef.current.longitude,
              }
            : undefined,
        });
        markerRef.current = currentMarker;
        clickListener = map.addListener("click", (event) => {
          if (!interactiveRef.current || !event.latLng) return;
          onMapPressRef.current?.({
            latitude: event.latLng.lat(),
            longitude: event.latLng.lng(),
          });
        });
      })
      .catch((error: unknown) => {
        if (!active) return;
        setLoadError(
          error instanceof GoogleMapsLoadError
            ? error.reason
            : "load-failed",
        );
      });

    return () => {
      active = false;
      clickListener?.remove();
      currentMarker?.setMap(null);
      mapRef.current = null;
      markerRef.current = null;
    };
  }, [locale]);

  useEffect(() => {
    mapRef.current?.setCenter({
      lat: center.latitude,
      lng: center.longitude,
    });
  }, [center.latitude, center.longitude]);

  useEffect(() => {
    markerRef.current?.setPosition(
      marker
        ? { lat: marker.latitude, lng: marker.longitude }
        : null,
    );
  }, [marker]);

  return (
    <View style={[styles.container, style]}>
      <div
        ref={elementRef}
        style={{
          position: "absolute",
          top: 0,
          right: 0,
          bottom: 0,
          left: 0,
        }}
      />
      {loadError ? (
        <Text accessibilityRole="alert" style={styles.error}>
          {loadError === "missing-key"
            ? t("map.webApiKeyMissing")
            : t("map.webMapLoadFailed")}
        </Text>
      ) : null}
    </View>
  );
}

const styles = StyleSheet.create({
  container: {
    minHeight: 180,
    overflow: "hidden",
    position: "relative",
    width: "100%",
  },
  error: {
    backgroundColor: "#FFF",
    color: "#555",
    left: 12,
    padding: 10,
    position: "absolute",
    right: 12,
    textAlign: "center",
    top: 12,
  },
});
