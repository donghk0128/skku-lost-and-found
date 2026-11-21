import { useState } from "react";
import { StyleSheet, View } from "react-native";
import MapCampusSwitch, { MAP_CAMPUSES, type MapCampus } from "@/components/MapCampusSwitch";
import GoogleMap from "@/components/GoogleMap.web";
import type { LocationEntry } from "@/lib/location-entries";
import type { MapCoordinates } from "@/lib/google-maps.web";

type Props = { locations: LocationEntry[]; activeId: string; disabled: boolean; onMapPress: (point: MapCoordinates) => void; onMarkerPress: (id: string) => void };
export default function ChatLocationsMap({ locations, activeId, disabled, onMapPress, onMarkerPress }: Props) {
  const [selectedCampus, setSelectedCampus] = useState<MapCampus | null>(null);
  const [cameraRequest, setCameraRequest] = useState<{ center: MapCoordinates; key: number }>();
  const switchCampus = (id: MapCampus) => {
    setSelectedCampus(id);
    setCameraRequest(current => ({ center: MAP_CAMPUSES[id], key: (current?.key ?? 0) + 1 }));
  };
  const points = locations.flatMap((row, index) => row.pin ? [{ id: row.id, latitude: row.pin.latitude, longitude: row.pin.longitude, label: String(index + 1), active: row.id === activeId }] : []);
  const center = cameraRequest?.center ?? points[0] ?? { latitude: 37.2939, longitude: 126.9751 };
  return <View style={styles.frame}><GoogleMap center={center} markers={points} fitMarkers={!cameraRequest} cameraRequest={cameraRequest} interactive={!disabled} onMapPress={onMapPress} onMarkerPress={id => { if (!disabled) onMarkerPress(id); }} style={{ height: 240, borderRadius: 12 }} /><MapCampusSwitch selected={selectedCampus} disabled={disabled} onSelect={switchCampus} /></View>;
}

const styles = StyleSheet.create({ frame: { width: "100%", height: 240, borderRadius: 12, overflow: "hidden" } });
