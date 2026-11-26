import { useFonts } from "expo-font";
import { DarkTheme, DefaultTheme, ThemeProvider, Stack, router, useRootNavigationState } from "expo-router";
import { useEffect } from "react";
import * as SplashScreen from "expo-splash-screen";
import { useColorScheme } from "react-native";

import { AnimatedSplashOverlay } from "@/components/animated-icon";
import { Fonts } from "@/constants/theme";
import AuthProvider, { useAuth } from "@/providers/AuthProvider";
import { LocaleProvider } from "@/i18n/LocaleProvider";
import { observePush } from "@/lib/push-client";

SplashScreen.preventAutoHideAsync();

function AuthContent() {
  const { user, loading } = useAuth();
  const navigation = useRootNavigationState();
  useEffect(() => {
    if (loading || !user || !navigation?.key) return;
    return observePush(user.id,
      id => router.push({ pathname: "/post/[id]", params: { id } }),
      id => router.push({ pathname: "/chat/[id]", params: { id } }));
  }, [user, loading, navigation?.key]);

  if (loading) return null;

  return (
    <Stack screenOptions={{ headerShown: false, animation: "slide_from_right", gestureEnabled: true, contentStyle: { backgroundColor: "#FFFFFF" } }}>
      <Stack.Protected guard={!!user}>
        <Stack.Screen name="(tabs)" />
        <Stack.Screen name="create-post-method" />
        <Stack.Screen name="create-post-ai" />
        <Stack.Screen name="create-post" />
        <Stack.Screen name="settings" />
        <Stack.Screen name="post/[id]" />
        <Stack.Screen name="chat/[id]" />
        <Stack.Screen name="profile-edit" />
        <Stack.Screen name="password-change" />
        <Stack.Screen name="my-posts" />
        <Stack.Screen name="favorites" />
        <Stack.Screen name="keyword-conditions" />
        <Stack.Screen name="withdrawal" />
      </Stack.Protected>
      <Stack.Protected guard={!user}>
        <Stack.Screen name="login" />
        <Stack.Screen name="password-reset" />
        <Stack.Screen name="signup" />
        <Stack.Screen name="signup-code" />
        <Stack.Screen name="signup-information" />
      </Stack.Protected>
    </Stack>
  );
}

export default function TabLayout() {
  const colorScheme = useColorScheme();
  const [fontsLoaded, fontError] = useFonts({
    [Fonts.pretendardRegular]: require("@/../assets/fonts/Pretendard-Regular.otf"),
    [Fonts.pretendardMedium]: require("@/../assets/fonts/Pretendard-Medium.otf"),
    [Fonts.pretendardSemiBold]: require("@/../assets/fonts/Pretendard-SemiBold.otf"),
    [Fonts.pretendardBold]: require("@/../assets/fonts/Pretendard-Bold.otf"),
  });

  if (!fontsLoaded && !fontError) return null;

  return (
    <LocaleProvider>
      <AuthProvider>
        <ThemeProvider value={colorScheme === "dark" ? DarkTheme : DefaultTheme}>
          <AnimatedSplashOverlay />
          <AuthContent />
        </ThemeProvider>
      </AuthProvider>
    </LocaleProvider>
  );
}
