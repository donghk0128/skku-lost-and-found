import { useState } from "react";
import { Modal, Pressable, StyleSheet, Text, View } from "react-native";
import { SafeAreaView } from "react-native-safe-area-context";
import PrivateChatImage from "@/components/PrivateChatImage";
import type { ChatMessageImage } from "@/lib/chat-api";
import { useLocale } from "@/i18n/LocaleProvider";

export default function ChatImageGallery({ images }: { images: ChatMessageImage[] }) {
  const { t } = useLocale();
  const [selected, setSelected] = useState<number | null>(null);
  return <>
    <View style={styles.grid}>{images.slice(0, 4).map((image, index) => <Pressable
      key={image.id} accessibilityRole="button" accessibilityLabel={t("chat.viewPhoto", { index: index + 1, total: images.length })}
      onPress={() => setSelected(index)}>
      <PrivateChatImage path={image.image_url} resizeMode={images.length === 1 ? "contain" : "cover"} style={images.length === 1 ? styles.single : styles.tile} />
      {index === 3 && images.length > 4 ? <View pointerEvents="none" style={styles.more}><Text style={styles.moreText}>+{images.length - 4}</Text></View> : null}
    </Pressable>)}</View>
    <Modal visible={selected !== null} transparent animationType="fade" onRequestClose={() => setSelected(null)}>
      <SafeAreaView style={styles.viewer}>
        <Pressable accessibilityRole="button" accessibilityLabel={t("common.close")} style={styles.close} onPress={() => setSelected(null)}><Text style={styles.label}>{t("common.close")}</Text></Pressable>
        {selected !== null && images[selected] ? <PrivateChatImage key={images[selected].id} path={images[selected].image_url} style={styles.full} /> : null}
        <View style={styles.navigation}>
          <Pressable accessibilityRole="button" accessibilityLabel={t("chat.previousPhoto")} disabled={selected === null || selected === 0} onPress={() => setSelected(index => index === null ? null : index - 1)} style={styles.control}><Text style={[styles.arrow, selected === 0 && styles.disabled]}>‹</Text></Pressable>
          <Text style={styles.label}>{selected === null ? "" : `${selected + 1} / ${images.length}`}</Text>
          <Pressable accessibilityRole="button" accessibilityLabel={t("chat.nextPhoto")} disabled={selected === null || selected === images.length - 1} onPress={() => setSelected(index => index === null ? null : index + 1)} style={styles.control}><Text style={[styles.arrow, selected === images.length - 1 && styles.disabled]}>›</Text></Pressable>
        </View>
      </SafeAreaView>
    </Modal>
  </>;
}

const styles = StyleSheet.create({
  grid: { width: 220, flexDirection: "row", flexWrap: "wrap", gap: 6 },
  single: { width: 220, height: 220 }, tile: { width: 107, height: 107, borderRadius: 8 },
  more: { position: "absolute", top: 0, bottom: 0, left: 0, right: 0, backgroundColor: "#00000088", borderRadius: 8, alignItems: "center", justifyContent: "center" },
  moreText: { color: "white", fontSize: 26 }, viewer: { flex: 1, backgroundColor: "#000000F2", padding: 16 },
  close: { alignSelf: "flex-end", padding: 16 }, label: { color: "white", fontSize: 15 },
  full: { flex: 1, width: "100%", height: undefined, backgroundColor: "transparent" },
  navigation: { flexDirection: "row", alignItems: "center", justifyContent: "space-between" },
  control: { padding: 18 }, arrow: { color: "white", fontSize: 36 }, disabled: { opacity: 0.25 },
});
