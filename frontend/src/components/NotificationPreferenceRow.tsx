import * as Notifications from "expo-notifications";
import * as SecureStore from "expo-secure-store";
import { useEffect, useRef, useState } from "react";
import { Alert, AppState, Linking, Platform, Pressable, StyleSheet, Text, View } from "react-native";

import { ProfileMenuIcon, profileMenuStyles as styles } from "@/components/profile-menu";
import { Colors } from "@/constants/theme";
import { useLocale } from "@/i18n/LocaleProvider";

const preferenceKey = "lost-found-notifications";

function allowsNotifications(permission: Notifications.NotificationPermissionsStatus) {
  return (
    permission.granted ||
    permission.ios?.status === Notifications.IosAuthorizationStatus.PROVISIONAL
  );
}

export default function NotificationPreferenceRow() {
  const { t } = useLocale();
  const [enabled, setEnabled] = useState(false);
  const [ready, setReady] = useState(false);
  const [saving, setSaving] = useState(false);
  const pending = useRef(false);
  const refreshVersion = useRef(0);

  useEffect(() => {
    if (Platform.OS !== "ios" && Platform.OS !== "android") return;

    let active = true;
    async function refresh() {
      if (pending.current) return;
      const version = ++refreshVersion.current;
      try {
        const [value, permission] = await Promise.all([
          SecureStore.getItemAsync(preferenceKey),
          Notifications.getPermissionsAsync(),
        ]);
        if (active && version === refreshVersion.current) {
          setEnabled(value === "on" && allowsNotifications(permission));
        }
      } catch {
        // Keep the last known value and allow the user to try again.
      } finally {
        if (active && version === refreshVersion.current) setReady(true);
      }
    }

    void refresh();
    const subscription = AppState.addEventListener("change", (state) => {
      if (state === "active") void refresh();
    });
    return () => {
      active = false;
      subscription.remove();
    };
  }, []);

  if (Platform.OS !== "ios" && Platform.OS !== "android") return null;

  async function setPreference(next: boolean) {
    if (pending.current) return;
    pending.current = true;
    ++refreshVersion.current;
    setSaving(true);
    try {
      if (next) {
        if (Platform.OS === "android") {
          await Notifications.setNotificationChannelAsync("default", {
            name: t("account.notifications"),
            importance: Notifications.AndroidImportance.DEFAULT,
          });
        }
        let permission = await Notifications.getPermissionsAsync();
        const previouslyBlocked = !permission.canAskAgain;
        if (!allowsNotifications(permission) && !previouslyBlocked) {
          permission = await Notifications.requestPermissionsAsync();
        }
        if (!allowsNotifications(permission)) {
          setEnabled(false);
          if (previouslyBlocked) {
            Alert.alert(t("account.notifications"), t("account.notificationPermissionBlocked"), [
              { text: t("common.cancel"), style: "cancel" },
              {
                text: t("settings.title"),
                onPress: () => {
                  void Linking.openSettings().catch(() => {
                    Alert.alert(t("account.notifications"), t("common.requestFailed"));
                  });
                },
              },
            ]);
          }
          return;
        }
      }

      await SecureStore.setItemAsync(preferenceKey, next ? "on" : "off");
      setEnabled(next);
    } catch {
      Alert.alert(t("account.notifications"), t("account.notificationSaveFailed"));
    } finally {
      pending.current = false;
      setSaving(false);
    }
  }

  const disabled = !ready || saving;
  return (
    <Pressable
      accessibilityRole="switch"
      accessibilityLabel={t("account.notifications")}
      accessibilityState={{ checked: enabled, disabled }}
      disabled={disabled}
      onPress={() => void setPreference(!enabled)}
      style={({ pressed }) => [styles.row, pressed && toggleStyles.pressed]}
    >
      <ProfileMenuIcon ios="bell" material="notifications" />
      <Text style={styles.label}>{t("account.notifications")}</Text>
      <View
        style={[toggleStyles.track, enabled && toggleStyles.enabled, disabled && toggleStyles.disabled]}
      >
        <View style={toggleStyles.thumb} />
      </View>
    </Pressable>
  );
}

const toggleStyles = StyleSheet.create({
  track: {
    width: 36,
    height: 20,
    marginEnd: 2,
    borderRadius: 10,
    backgroundColor: "#798A82",
    justifyContent: "center",
    alignItems: "flex-start",
    paddingHorizontal: 2,
  },
  enabled: { backgroundColor: Colors.primary, alignItems: "flex-end" },
  disabled: { opacity: 0.5 },
  thumb: { width: 16, height: 16, borderRadius: 8, backgroundColor: "#FFFFFF" },
  pressed: { backgroundColor: "#F4F8F6" },
});
