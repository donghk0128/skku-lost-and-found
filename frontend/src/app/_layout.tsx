import { useFonts } from "expo-font";
import { DarkTheme, DefaultTheme, ThemeProvider } from "expo-router";
import * as SplashScreen from "expo-splash-screen";
import { useColorScheme } from "react-native";

import { AnimatedSplashOverlay } from "@/components/animated-icon";
import AppTabs from "@/components/app-tabs";
import { Fonts } from "@/constants/theme";
import AuthProvider, { useAuth } from "@/providers/AuthProvider";
import Login from "@/app/login";

SplashScreen.preventAutoHideAsync();

function AuthContent() {
  const { user, loading } = useAuth();

  if (loading) return null; // 또는 로딩 화면

  return user ? <AppTabs /> : <Login />;
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
