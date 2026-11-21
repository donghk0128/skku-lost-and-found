import type { ReactNode } from "react";
import { Pressable, StyleSheet, Text, TextInput, View } from "react-native";
import { Colors } from "@/constants/theme";
import { useLocale } from "@/i18n/LocaleProvider";
import NavigationIcon from "@/assets/icons/navigation.svg";

type Props = {
  value: string;
  onChangeText: (value: string) => void;
  onSend: () => void;
  onAttach: () => void;
  inputDisabled?: boolean;
  attachmentDisabled?: boolean;
  sendDisabled: boolean;
  busy?: boolean;
  placeholder?: string;
  inputAccessibilityLabel?: string;
  attachAccessibilityLabel?: string;
  sendAccessibilityLabel?: string;
  attachmentIcon?: ReactNode;
  maxLength?: number;
};

export default function ChatComposer({
  value,
  onChangeText,
  onSend,
  onAttach,
  inputDisabled = false,
  attachmentDisabled = inputDisabled,
  sendDisabled,
  busy = false,
  placeholder,
  inputAccessibilityLabel,
  attachAccessibilityLabel,
  sendAccessibilityLabel,
  attachmentIcon,
  maxLength,
}: Props) {
  const { t } = useLocale();
  return (
    <View style={styles.composer}>
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={attachAccessibilityLabel ?? t("chat.attach")}
        accessibilityState={{ disabled: attachmentDisabled }}
        disabled={attachmentDisabled}
        onPress={onAttach}
        style={[styles.attachButton, attachmentDisabled && styles.disabled]}
      >
        {attachmentIcon ?? <Text style={styles.attach}>＋</Text>}
      </Pressable>
      <TextInput
        accessibilityLabel={inputAccessibilityLabel ?? t("chat.placeholder")}
        placeholder={placeholder ?? t("chat.placeholder")}
        value={value}
        onChangeText={onChangeText}
        maxLength={maxLength}
        multiline
        editable={!inputDisabled}
        style={styles.input}
      />
      <Pressable
        accessibilityRole="button"
        accessibilityLabel={sendAccessibilityLabel ?? t("chat.send")}
        accessibilityState={{ disabled: sendDisabled, busy }}
        disabled={sendDisabled}
        onPress={onSend}
        style={[styles.send, sendDisabled && styles.disabled]}
      >
        <NavigationIcon width={20} height={20} color="white" />
      </Pressable>
    </View>
  );
}

const styles = StyleSheet.create({
  composer: {
    flexDirection: "row",
    alignItems: "flex-end",
    gap: 10,
    padding: 14,
  },
  attachButton: {
    minWidth: 28,
    minHeight: 44,
    alignItems: "center",
    justifyContent: "center",
  },
  attach: { fontSize: 28, color: Colors.primary, paddingVertical: 4 },
  input: {
    flex: 1,
    maxHeight: 120,
    minHeight: 44,
    padding: 12,
    backgroundColor: "#F0F4F1",
    borderRadius: 16,
    fontSize: 15,
  },
  send: {
    backgroundColor: Colors.primary,
    padding: 10,
    borderRadius: 1000,
    alignItems: "center",
    justifyContent: "center",
  },
  sendText: { color: "white", fontSize: 14 },
  disabled: { opacity: 0.4 },
});
