import { useFonts } from "expo-font";
import { DarkTheme, DefaultTheme, ThemeProvider, Stack } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import { useColorScheme } from "react-native";

import { AnimatedSplashOverlay } from "@/components/animated-icon";
import { Fonts } from "@/constants/theme";
import AuthProvider, { useAuth } from "@/providers/AuthProvider";

SplashScreen.preventAutoHideAsync();

function AuthContent() {
  const { user, loading } = useAuth();

  if (loading) return null; // 또는 로딩 화면

  return (
    <Stack screenOptions={{ headerShown: false, animation: "slide_from_right", gestureEnabled: true, contentStyle: { backgroundColor: "#FFFFFF" } }}>
      <Stack.Protected guard={!!user}>
        <Stack.Screen name="(tabs)" />
        <Stack.Screen name="create-post-method" />
        <Stack.Screen name="create-post-ai" />
        <Stack.Screen name="create-post" />
        <Stack.Screen name="settings" />
        <Stack.Screen name="post/[id]" />
      </Stack.Protected>
      <Stack.Protected guard={!user}>
        <Stack.Screen name="login" />
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
    <AuthProvider>
      <ThemeProvider value={colorScheme === "dark" ? DarkTheme : DefaultTheme}>
        <AnimatedSplashOverlay />
        <AuthContent />
      </ThemeProvider>
    </AuthProvider>
  );
}
