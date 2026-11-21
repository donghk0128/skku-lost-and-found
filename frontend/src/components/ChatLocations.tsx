import { useId, useRef, useState } from "react";
import { Keyboard, Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import Svg, { Path } from "react-native-svg";
import ChatLocationsMap from "@/components/ChatLocationsMap";
import XIcon from "@/assets/icons/x.svg";
import { Colors, Fonts } from "@/constants/theme";
import { useLocale } from "@/i18n/LocaleProvider";
import type { LocationEntry } from "@/lib/location-entries";
import type { MapCoordinates } from "@/lib/google-maps.web";

export default function ChatLocations({ locations, onChange, onConfirm, onSkip, confirmed, disabled }: {
  locations: LocationEntry[];
  onChange: (locations: LocationEntry[]) => void;
  onConfirm: (locations: LocationEntry[]) => void;
  onSkip: () => void;
  confirmed: boolean;
  disabled: boolean;
}) {
  const { t } = useLocale();
  const scope = useId();
  const sequence = useRef(0);
  const [activeId, setActiveId] = useState(locations[0]?.id ?? "");
  const [editingId, setEditingId] = useState<string | null>(null);
  const index = Math.max(0, locations.findIndex(row => row.id === activeId));
  const current = locations[index];
  if (!current) return null;
  const complete = locations.every(row => Boolean(row.pin));
  const select = (id: string) => { Keyboard.dismiss(); setEditingId(null); setActiveId(id); };
  const placePin = (point: MapCoordinates) => {
    const latitude = Number(point.latitude.toFixed(6));
    const longitude = Number(point.longitude.toFixed(6));
    const address = current.text.trim() || `${latitude}, ${longitude}`;
    onChange(locations.map(row => row.id === current.id ? { ...row, text: address, pin: { address, latitude, longitude } } : row));
  };
  return (
    <View style={styles.card}>
      <View style={styles.heading}>
        <Text style={styles.title}>{t("ai.addMapTitle")}</Text>
        <Text style={styles.progress}>{index + 1}/{locations.length}</Text>
      </View>
      <ChatLocationsMap locations={locations} activeId={current.id} disabled={disabled} onMapPress={placePin} onMarkerPress={select} />
      <View style={styles.list}>
        {locations.map((row, rowIndex) => {
          const active = row.id === current.id;
          return <View key={row.id} style={styles.entry}>
            <View style={[styles.listRow, active && styles.activeRow]}>
              <Pressable accessibilityRole="button" accessibilityLabel={`${rowIndex + 1}. ${row.text || t("ai.unnamedLocation")}`} accessibilityState={{ selected: active, disabled }} disabled={disabled} onPress={() => select(row.id)} style={styles.selectRow}>
                <View style={[styles.number, active && styles.activeNumber]}><Text style={[styles.numberText, active && styles.activeNumberText]}>{rowIndex + 1}</Text></View>
                <Text numberOfLines={2} style={[styles.name, active && styles.activeName]}>{row.text || t("ai.unnamedLocation")}</Text>
              </Pressable>
              <Pressable accessibilityRole="button" accessibilityLabel={t("ai.editLocationName", { index: rowIndex + 1 })} disabled={disabled} onPress={() => { setActiveId(row.id); setEditingId(row.id); }} style={styles.iconButton}>
                <Svg width={15} height={15} viewBox="0 0 24 24" fill="none" stroke="#819086" strokeWidth={1.6} strokeLinecap="round" strokeLinejoin="round"><Path d="m15 4 5 5M4 20l4-1 12-12a2 2 0 0 0-4-4L4 15v5Z" /></Svg>
              </Pressable>
              {locations.length > 1 ? <Pressable accessibilityRole="button" accessibilityLabel={t("createPost.removeLocation", { index: rowIndex + 1 })} disabled={disabled} onPress={() => { const next = locations.filter(item => item.id !== row.id); onChange(next); if (active) select(next[Math.min(rowIndex, next.length - 1)].id); }} style={styles.iconButton}><XIcon width={15} height={15} color="#819086" /></Pressable> : null}
            </View>
            {editingId === row.id ? <TextInput autoFocus accessibilityLabel={t("createPost.locationNumber", { index: rowIndex + 1 })} value={row.text} onChangeText={text => onChange(locations.map(item => item.id === row.id ? { ...item, text, pin: null } : item))} editable={!disabled} maxLength={255} placeholder={t("createPost.locationExample")} placeholderTextColor="#AAB2AD" returnKeyType="done" onSubmitEditing={() => setEditingId(null)} onBlur={() => setEditingId(null)} style={styles.input} /> : null}
          </View>;
        })}
        <Pressable accessibilityRole="button" disabled={disabled} onPress={() => { const id = `${scope}-${++sequence.current}`; onChange([...locations, { id, text: "", pin: null }]); setActiveId(id); setEditingId(id); }} style={styles.add}>
          <Svg width={15} height={15} viewBox="0 0 24 24" fill="none" stroke={Colors.primary} strokeWidth={1.8} strokeLinecap="round"><Path d="M12 5v14M5 12h14" /></Svg>
          <Text style={styles.addText}>{t("createPost.addLocation")}</Text>
        </Pressable>
      </View>
      <Pressable accessibilityRole="button" accessibilityState={{ disabled: disabled || !complete, selected: confirmed }} disabled={disabled || !complete} onPress={() => onConfirm(locations)} style={[styles.confirm, (disabled || !complete) && styles.disabled]}>
        <Text style={styles.confirmText}>{t("ai.confirmLocations")}</Text>
      </Pressable>
      <Pressable accessibilityRole="button" disabled={disabled} onPress={() => { Keyboard.dismiss(); onSkip(); }} style={styles.skip}><Text style={styles.skipText}>{t("ai.skipMap")}</Text></Pressable>
    </View>
  );
}
const styles = StyleSheet.create({
  card: { alignSelf: "stretch", backgroundColor: "#F5F8F6", borderRadius: 16, padding: 12, gap: 10 },
  heading: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  title: { fontFamily: Fonts.pretendardSemiBold, fontSize: 15, color: "#29372F" },
  progress: { fontFamily: Fonts.pretendardMedium, fontSize: 12, color: "#849189" },
  list: { gap: 4 },
  entry: { gap: 6 },
  listRow: { flexDirection: "row", alignItems: "center", borderRadius: 10 },
  activeRow: { backgroundColor: Colors.softgreen },
  selectRow: { flex: 1, minHeight: 48, flexDirection: "row", alignItems: "center", gap: 9, paddingLeft: 8, paddingVertical: 8 },
  number: { width: 24, height: 24, borderRadius: 8, backgroundColor: "#E9EEEB", alignItems: "center", justifyContent: "center" },
  activeNumber: { backgroundColor: Colors.primary },
  numberText: { fontFamily: Fonts.pretendardMedium, fontSize: 12, color: "#7E8E83" },
  activeNumberText: { color: "white" },
  name: { flex: 1, fontFamily: Fonts.pretendardRegular, fontSize: 13, lineHeight: 19, color: "#65766B" },
  activeName: { color: Colors.primary, fontFamily: Fonts.pretendardMedium },
  iconButton: { width: 28, minHeight: 44, alignItems: "center", justifyContent: "center" },
  input: { minHeight: 44, backgroundColor: "white", borderWidth: 1, borderColor: "#DDE5DF", borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10, fontFamily: Fonts.pretendardRegular, fontSize: 13, color: "#34453A" },
  add: { minHeight: 40, flexDirection: "row", alignItems: "center", gap: 6, paddingLeft: 8 },
  addText: { fontFamily: Fonts.pretendardMedium, fontSize: 13, color: Colors.primary },
  confirm: { minHeight: 44, alignItems: "center", justifyContent: "center", borderRadius: 10, padding: 10, backgroundColor: Colors.primary },
  confirmText: { fontFamily: Fonts.pretendardMedium, fontSize: 13, color: "white" },
  skip: { alignSelf: "center", minHeight: 36, paddingHorizontal: 16, justifyContent: "center" },
  skipText: { fontFamily: Fonts.pretendardRegular, fontSize: 12, color: "#8C9890" },
  disabled: { opacity: 0.4 },
});
