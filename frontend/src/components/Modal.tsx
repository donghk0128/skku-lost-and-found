import type { ReactNode } from "react";
import {
  Modal as NativeModal,
  Pressable,
  StyleSheet,
  Text,
  View,
} from "react-native";

import { Colors, Fonts } from "@/constants/theme";
import { useLocale } from "@/i18n/LocaleProvider";

export type ModalProps = {
  visible: boolean;
  title: string;
  description?: string;
  /** Omit to render the dialog without an icon or its reserved space. */
  icon?: ReactNode;
  confirmLabel: string;
  cancelLabel?: string;
  loading?: boolean;
  confirmDisabled?: boolean;
  errorMessage?: string;
  onConfirm: () => void;
  onClose: () => void;
};

export default function Modal({
  visible,
  title,
  description,
  icon,
  confirmLabel,
  cancelLabel,
  loading = false,
  confirmDisabled = false,
  errorMessage,
  onConfirm,
  onClose,
}: ModalProps) {
  const { t } = useLocale();
  const cancelText = cancelLabel ?? t("common.cancel");
  const requestClose = () => {
    if (!loading) onClose();
  };

  return (
    <NativeModal
      visible={visible}
      transparent
      animationType="fade"
      statusBarTranslucent
      onRequestClose={requestClose}
    >
      <View style={styles.overlay}>
        <Pressable
          style={StyleSheet.absoluteFill}
          accessibilityRole="button"
          accessibilityLabel={cancelText}
          disabled={loading}
          onPress={requestClose}
        />
        <View
          style={styles.card}
          accessibilityViewIsModal
          onAccessibilityEscape={requestClose}
        >
          {icon ? (
            <View
              style={styles.icon}
              accessibilityElementsHidden
              importantForAccessibility="no-hide-descendants"
            >
              {icon}
            </View>
          ) : null}
          <Text accessibilityRole="header" style={styles.title}>
            {title}
          </Text>
          {description ? <Text style={styles.description}>{description}</Text> : null}
          {errorMessage ? <Text accessibilityRole="alert" style={styles.error}>{errorMessage}</Text> : null}
          <View style={styles.actions}>
            <Pressable
              accessibilityRole="button"
              disabled={loading}
          onPress={requestClose}
              style={({ pressed }) => [styles.button, pressed && styles.pressed]}
            >
              <Text style={styles.cancelText}>{cancelText}</Text>
            </Pressable>
            <Pressable
              accessibilityRole="button"
              accessibilityState={{ disabled: loading || confirmDisabled, busy: loading }}
              disabled={loading || confirmDisabled}
              onPress={onConfirm}
              style={({ pressed }) => [styles.button, (loading || confirmDisabled) && styles.disabled, pressed && styles.pressed]}
            >
              <Text style={styles.confirmText}>{confirmLabel}</Text>
            </Pressable>
          </View>
        </View>
      </View>
    </NativeModal>
  );
}

const styles = StyleSheet.create({
  overlay: {
    flex: 1,
    justifyContent: "center",
    alignItems: "center",
    padding: 20,
    backgroundColor: "rgba(0,0,0,0.55)",
  },
  card: {
    width: "100%",
    maxWidth: 400,
    padding: 24,
    borderRadius: 14,
    backgroundColor: "white",
    alignItems: "flex-start",
    gap: 14,
  },
  icon: {
    width: 44,
    height: 44,
    borderRadius: 22,
    backgroundColor: Colors.softgreen,
    alignItems: "center",
    justifyContent: "center",
    marginBottom: 2,
  },
  title: {
    fontFamily: Fonts.pretendardSemiBold,
    fontSize: 20,
    lineHeight: 28,
    color: "#111",
    textAlign: "left",
  },
  description: {
    fontFamily: Fonts.pretendardRegular,
    fontSize: 14,
    lineHeight: 23,
    color: "#737E8D",
    textAlign: "left",
  },
  actions: {
    width: "100%",
    flexDirection: "row",
    justifyContent: "flex-end",
    gap: 12,
    marginTop: 4,
  },
  button: {
    minHeight: 44,
    minWidth: 64,
    paddingHorizontal: 10,
    paddingVertical: 10,
    alignItems: "center",
    justifyContent: "center",
    borderRadius: 8,
  },
  confirmText: {
    fontFamily: Fonts.pretendardSemiBold,
    fontSize: 15,
    color: Colors.primary,
  },
  cancelText: {
    fontFamily: Fonts.pretendardMedium,
    fontSize: 15,
    color: "#566171",
  },
  error: { color: "#B54747", fontFamily: Fonts.pretendardRegular, fontSize: 13, lineHeight: 20 },
  disabled: { opacity: 0.4 },
  pressed: { opacity: 0.6, backgroundColor: "#F5F6FA" },
});
