import { Platform, StyleSheet } from "react-native";

import { MaxContentWidth } from "@/constants/theme";

export const tabHeaderStyles = StyleSheet.create({
  container: {
    width: "100%",
    maxWidth: MaxContentWidth,
    alignSelf: "center",
    paddingHorizontal: 24,
  },
  row: {
    minHeight: 44,
    marginTop: Platform.OS === "web" ? 84 : 16,
    flexDirection: "row",
    alignItems: "center",
    justifyContent: "space-between",
  },
});
