import { SymbolView, type SymbolViewProps } from "expo-symbols";
import { Pressable, StyleSheet, Text, View } from "react-native";

import { Colors, Fonts } from "@/constants/theme";

type CrossPlatformName = Extract<SymbolViewProps["name"], object>;
type MenuIcon = { ios: NonNullable<CrossPlatformName["ios"]>; material: NonNullable<CrossPlatformName["android"]> };

export function ProfileMenuIcon({ ios, material, danger = false }: MenuIcon & { danger?: boolean }) {
  return (
    <View style={[styles.icon, danger && styles.dangerIcon]} accessible={false}>
      <SymbolView
        name={{ ios, android: material, web: material }}
        size={17}
        tintColor={danger ? "#A74747" : Colors.primary}
      />
    </View>
  );
}

export function ProfileMenuItem({ label, onPress, danger = false, ...icon }: MenuIcon & {
  label: string;
  onPress: () => void;
  danger?: boolean;
}) {
  return (
    <Pressable
      accessibilityRole="button"
      onPress={onPress}
      style={({ pressed }) => [profileMenuStyles.row, pressed && styles.pressed]}
    >
      <ProfileMenuIcon {...icon} danger={danger} />
      <Text style={[profileMenuStyles.label, danger && styles.dangerLabel]}>{label}</Text>
      <SymbolView name={{ ios: "chevron.right", android: "chevron_right", web: "chevron_right" }} size={15} tintColor="#657B72" />
    </Pressable>
  );
}

export const profileMenuStyles = StyleSheet.create({
  row: {
    minHeight: 57,
    paddingHorizontal: 14,
    paddingVertical: 8,
    flexDirection: "row",
    alignItems: "center",
    gap: 12,
  },
  label: { flex: 1, color: "#20372B", fontSize: 15, fontFamily: Fonts.pretendardMedium },
});

const styles = StyleSheet.create({
  icon: {
    width: 34,
    height: 34,
    borderRadius: 10,
    backgroundColor: "#EDF5F1",
    alignItems: "center",
    justifyContent: "center",
  },
  pressed: { backgroundColor: "#F4F8F6" },
  dangerIcon: { backgroundColor: "#FBF1F1" },
  dangerLabel: { color: "#A74747" },
});
