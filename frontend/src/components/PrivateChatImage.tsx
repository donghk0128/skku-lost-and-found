import { useEffect, useState } from "react";
import { Image, Platform, Pressable, StyleSheet, Text } from "react-native";
import type { ImageStyle, StyleProp } from "react-native";
import { ApiError } from "@/lib/auth-api";
import { imageUrl } from "@/lib/posts-api";
import { chatToken, withChatToken } from "@/lib/chat-api";
import { useLocale } from "@/i18n/LocaleProvider";

export default function PrivateChatImage({ path, style, resizeMode = "contain" }: { path: string; style?: StyleProp<ImageStyle>; resizeMode?: "contain" | "cover" }) {
  const { t } = useLocale();
  const [source, setSource] = useState<{ uri: string; headers?: Record<string, string> }>();
  const [failed, setFailed] = useState(false);
  const [attempt, setAttempt] = useState(0);
  useEffect(() => {
    let active = true;
    let objectUrl: string | undefined;
    const load = async () => {
      if (Platform.OS === "web") {
        const blob = await withChatToken(async token => {
          const response = await fetch(imageUrl(path), { headers: { Authorization: `Bearer ${token}` } });
          if (!response.ok) throw new ApiError(response.status, t("common.imageLoadFailed"));
          return response.blob();
        });
        if (!active) return;
        objectUrl = URL.createObjectURL(blob);
        setSource({ uri: objectUrl }); setFailed(false);
      } else {
        const token = await chatToken(true);
        if (active) { setSource({ uri: imageUrl(path), headers: { Authorization: `Bearer ${token}` } }); setFailed(false); }
      }
    };
    void load().catch(() => { if (active) setFailed(true); });
    return () => { active = false; if (objectUrl) URL.revokeObjectURL(objectUrl); };
  }, [path, attempt, t]);
  if (failed) return <Pressable onPress={() => setAttempt(value => value + 1)}><Text>{t("common.imageLoadFailed")}</Text></Pressable>;
  return <Image accessibilityLabel={t("chat.photo")} source={source} resizeMode={resizeMode} style={[styles.image, style]} onError={() => setFailed(true)} />;
}
const styles = StyleSheet.create({ image: { width: 220, height: 220, borderRadius: 12, backgroundColor: "#EEF3EF" } });
