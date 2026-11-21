import { Pressable, StyleSheet, Text, View } from "react-native";
import { Colors, Fonts } from "@/constants/theme";
import { useLocale } from "@/i18n/LocaleProvider";

export const MAP_CAMPUSES = {
  humanities: { latitude: 37.5882, longitude: 126.9933 },
  science: { latitude: 37.2939, longitude: 126.9751 },
};
export type MapCampus = keyof typeof MAP_CAMPUSES;

export default function MapCampusSwitch({ selected, disabled, onSelect }: {
  selected: MapCampus | null;
  disabled: boolean;
  onSelect: (campus: MapCampus) => void;
}) {
  const { t } = useLocale();
  return <View style={[styles.switch, disabled && styles.disabled]}>
    {(["humanities", "science"] as const).map(campus => <Pressable key={campus} accessibilityRole="button" accessibilityLabel={t(campus === "humanities" ? "map.humanitiesCampus" : "map.scienceCampus")} accessibilityState={{ selected: campus === selected, disabled }} disabled={disabled} onPress={() => onSelect(campus)} style={({ pressed }) => [styles.button, campus === selected && styles.selected, pressed && styles.pressed]}>
      <Text style={[styles.text, campus === selected && styles.selectedText]}>{t(campus === "humanities" ? "map.humanitiesShort" : "map.scienceShort")}</Text>
    </Pressable>)}
  </View>;
}
const styles = StyleSheet.create({
  switch: { position: "absolute", top: 10, left: 10, zIndex: 3, elevation: 3, flexDirection: "row", gap: 2, padding: 3, borderRadius: 12, backgroundColor: "white", borderWidth: 1, borderColor: "#E1E7E3", shadowColor: "#000", shadowOffset: { width: 0, height: 2 }, shadowOpacity: 0.08, shadowRadius: 5 },
  button: { minHeight: 36, paddingHorizontal: 12, paddingVertical: 8, borderRadius: 9, alignItems: "center", justifyContent: "center" },
  selected: { backgroundColor: Colors.softgreen },
  text: { fontFamily: Fonts.pretendardMedium, fontSize: 12, color: "#66786D" },
  selectedText: { color: Colors.primary },
  pressed: { opacity: 0.6 },
  disabled: { opacity: 0.5 },
});
