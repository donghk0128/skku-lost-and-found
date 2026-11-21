import { useCallback, useEffect, useRef, useState } from "react";
import { StyleSheet, Text, View } from "react-native";
import MapView, { Marker, PROVIDER_GOOGLE } from "react-native-maps";
import MapCampusSwitch, { MAP_CAMPUSES, type MapCampus } from "@/components/MapCampusSwitch";
import { Colors, Fonts } from "@/constants/theme";
import type { LocationEntry } from "@/lib/location-entries";
import type { MapCoordinates } from "@/lib/google-maps.web";

type Props = { locations: LocationEntry[]; activeId: string; disabled: boolean; onMapPress: (point: MapCoordinates) => void; onMarkerPress: (id: string) => void };
const campus = { latitude: 37.2939, longitude: 126.9751, latitudeDelta: 0.02, longitudeDelta: 0.02 };

export default function ChatLocationsMap({ locations, activeId, disabled, onMapPress, onMarkerPress }: Props) {
  const map = useRef<MapView>(null);
  const [selectedCampus, setSelectedCampus] = useState<MapCampus | null>(null);
  const campusChosen = useRef(false);
  const switchCampus = (id: MapCampus) => {
    campusChosen.current = true;
    setSelectedCampus(id);
    map.current?.animateToRegion({ ...MAP_CAMPUSES[id], latitudeDelta: 0.015, longitudeDelta: 0.015 }, 350);
  };
  const fit = useCallback(() => {
    if (campusChosen.current) return;
    const points = locations.flatMap(row => row.pin ? [{ latitude: row.pin.latitude, longitude: row.pin.longitude }] : []);
    if (points.length > 1) map.current?.fitToCoordinates(points, { edgePadding: { top: 40, left: 35, right: 35, bottom: 40 }, animated: true });
    else if (points[0]) map.current?.animateToRegion({ ...campus, ...points[0], latitudeDelta: 0.006, longitudeDelta: 0.006 }, 250);
  }, [locations]);
  useEffect(() => { fit(); }, [fit]);
  return <View style={styles.frame}><MapView ref={map} provider={PROVIDER_GOOGLE} style={styles.map} initialRegion={campus} onMapReady={fit} scrollEnabled={!disabled} zoomEnabled={!disabled} onPress={event => { if (!disabled) onMapPress(event.nativeEvent.coordinate); }}>
    {locations.map((row, index) => row.pin ? <Marker key={row.id} coordinate={row.pin} title={row.text} onPress={event => { event.stopPropagation(); if (!disabled) onMarkerPress(row.id); }}>
      <View style={[styles.marker, row.id === activeId && styles.active]}><Text style={styles.number}>{index + 1}</Text></View>
    </Marker> : null)}
  </MapView><MapCampusSwitch selected={selectedCampus} disabled={disabled} onSelect={switchCampus} /></View>;
}
const styles = StyleSheet.create({
  frame: { width: "100%", height: 240, borderRadius: 12, overflow: "hidden" },
  map: { width: "100%", height: 240, borderRadius: 12 },
  marker: { width: 30, height: 30, borderRadius: 15, backgroundColor: "#83988A", borderWidth: 2, borderColor: "white", alignItems: "center", justifyContent: "center" },
  active: { backgroundColor: Colors.primary },
  number: { color: "white", fontSize: 12, fontFamily: Fonts.pretendardSemiBold },
});
