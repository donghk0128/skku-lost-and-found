import { useState } from "react";
import { Pressable, StyleSheet, Text, View } from "react-native";
import { Colors, Fonts } from "@/constants/theme";
import { useLocale } from "@/i18n/LocaleProvider";
import type { LocationOption } from "@/lib/ai-api";

export default function ChatLocationOptions({ options, initialSelectedIds = [], disabled, onConfirm }: {
  options: LocationOption[];
  initialSelectedIds?: string[];
  disabled: boolean;
  onConfirm: (ids: string[]) => void;
}) {
  const { t } = useLocale();
  const [selectedIds, setSelectedIds] = useState(initialSelectedIds);
  const selected = options.filter(option => selectedIds.includes(option.id));
  return (
    <View style={styles.card}>
      <Text style={styles.hint}>{t("ai.locationOptionsHint")}</Text>
      <View style={styles.options}>
        {options.map((option, index) => {
          const checked = selectedIds.includes(option.id);
          return <Pressable key={option.id} accessibilityRole="checkbox" accessibilityLabel={option.label} accessibilityState={{ checked, disabled }} disabled={disabled} onPress={() => setSelectedIds(current => checked ? current.filter(id => id !== option.id) : [...current, option.id])} style={({ pressed }) => [styles.option, checked && styles.optionSelected, pressed && styles.pressed]}>
            <View style={[styles.checkbox, checked && styles.checked]}>{checked ? <Text style={styles.check}>✓</Text> : null}</View>
            <Text style={[styles.label, checked && styles.labelSelected]}>{index + 1}. {option.label}</Text>
          </Pressable>;
        })}
      </View>
      <Pressable accessibilityRole="button" accessibilityState={{ disabled: disabled || !selected.length }} disabled={disabled || !selected.length} onPress={() => onConfirm(selected.map(option => option.id))} style={[styles.confirm, (disabled || !selected.length) && styles.disabled]}>
        <Text style={styles.confirmText}>{t("ai.confirmLocationOptions")}</Text>
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  card: { alignSelf: "stretch", borderRadius: 16, backgroundColor: "#F5F8F6", padding: 12, gap: 10 },
  hint: { fontFamily: Fonts.pretendardRegular, fontSize: 12, lineHeight: 18, color: "#7A857E" },
  options: { gap: 7 },
  option: { minHeight: 44, flexDirection: "row", alignItems: "center", gap: 9, backgroundColor: "white", borderWidth: 1, borderColor: "#E1E7E3", borderRadius: 10, paddingHorizontal: 12, paddingVertical: 10 },
  optionSelected: { backgroundColor: Colors.softgreen, borderColor: Colors.primary },
  checkbox: { width: 18, height: 18, borderWidth: 1, borderColor: "#BAC6BD", borderRadius: 5, alignItems: "center", justifyContent: "center" },
  checked: { backgroundColor: Colors.primary, borderColor: Colors.primary },
  check: { color: "white", fontSize: 12 },
  label: { flex: 1, fontFamily: Fonts.pretendardRegular, fontSize: 13, lineHeight: 19, color: "#45534A" },
  labelSelected: { color: Colors.primary, fontFamily: Fonts.pretendardMedium },
  confirm: { minHeight: 44, alignItems: "center", justifyContent: "center", borderRadius: 10, backgroundColor: Colors.primary, padding: 10 },
  confirmText: { fontFamily: Fonts.pretendardMedium, fontSize: 13, color: "white" },
  disabled: { opacity: 0.45 },
  pressed: { opacity: 0.7 },
});
