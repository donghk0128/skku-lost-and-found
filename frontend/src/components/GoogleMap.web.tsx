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

export type MapMarkerPoint = MapCoordinates & { id: string; label: string; active?: boolean };

type Props = {
  center: MapCoordinates;
  marker?: MapCoordinates | null;
  markers?: MapMarkerPoint[];
  fitMarkers?: boolean;
  cameraRequest?: { center: MapCoordinates; key: number };
  onMarkerPress?: (id: string) => void;
  interactive?: boolean;
  onMapPress?: (coordinates: MapCoordinates) => void;
  style?: StyleProp<ViewStyle>;
};

export default function GoogleMap({
  center,
  marker = null,
  markers,
  fitMarkers = false,
  cameraRequest,
  onMarkerPress,
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
  const [mapVersion, setMapVersion] = useState(0);
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
        setMapVersion(version => version + 1);
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

  useEffect(() => {
    const map = mapRef.current;
    const google = window.google;
    if (!map || !google || !markers) return;
    const rendered = markers.map(point => {
      const pin = new google.maps.Marker({
        map,
        position: { lat: point.latitude, lng: point.longitude },
        label: { text: point.label, color: "white", fontSize: "12px", fontWeight: "600" },
        icon: { path: "M 0,-14 A 14,14 0 1 0 0,14 A 14,14 0 1 0 0,-14", fillColor: point.active ? "#00785D" : "#83988A", fillOpacity: 1, strokeColor: "white", strokeWeight: 2, scale: 1 },
      });
      const listener = pin.addListener("click", () => onMarkerPress?.(point.id));
      return { pin, listener };
    });
    if (fitMarkers && markers.length > 1) {
      const latitudes = markers.map(point => point.latitude);
      const longitudes = markers.map(point => point.longitude);
      map.fitBounds({ north: Math.max(...latitudes) + 0.0002, south: Math.min(...latitudes) - 0.0002, east: Math.max(...longitudes) + 0.0002, west: Math.min(...longitudes) - 0.0002 }, 32);
    }
    return () => rendered.forEach(({ pin, listener }) => { listener.remove(); pin.setMap(null); });
  }, [markers, fitMarkers, onMarkerPress, mapVersion]);

  useEffect(() => {
    if (!cameraRequest || !mapRef.current) return;
    mapRef.current.setCenter({ lat: cameraRequest.center.latitude, lng: cameraRequest.center.longitude });
    mapRef.current.setZoom(15);
  }, [cameraRequest, mapVersion]);

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
