// Keep service credentials out of this client configuration.
const { existsSync } = require("node:fs");
const { dirname, join } = require("node:path");

module.exports = ({ config }) => {
  const googleMapsApiKey = process.env.EXPO_PUBLIC_GOOGLE_MAPS_API_KEY;
  const projectId = process.env.EAS_PROJECT_ID || config.extra?.eas?.projectId;
  const iosGoogleServices = process.env.GOOGLE_SERVICES_IOS || config.ios?.googleServicesFile
    || (existsSync(join(dirname(require.resolve("./app.json")), "GoogleService-Info.plist")) ? "./GoogleService-Info.plist" : undefined);

  return {
    ...config,
    ...(process.env.EAS_PROJECT_OWNER ? { owner: process.env.EAS_PROJECT_OWNER } : {}),
    extra: {
      ...config.extra,
      ...(projectId ? { eas: { ...config.extra?.eas, projectId } } : {}),
    },
    ios: {
      ...config.ios,
      ...(iosGoogleServices ? { googleServicesFile: iosGoogleServices } : {}),
    },
    android: {
      ...config.android,
      googleServicesFile: process.env.GOOGLE_SERVICES_ANDROID || config.android?.googleServicesFile || "./google-services.json",
      config: {
        ...config.android?.config,
        googleMaps: { apiKey: googleMapsApiKey },
      },
    },
    plugins: [
      ...(config.plugins ?? []),
      "@react-native-firebase/app",
      ["@react-native-firebase/messaging", { installationIdEnabled: true }],
      ["expo-build-properties", { ios: { useFrameworks: "dynamic" } }],
      ["expo-notifications", {
        icon: "./assets/images/android-icon-monochrome.png",
        color: "#208AEF",
        defaultChannel: "keyword-posts",
        enableBackgroundRemoteNotifications: true,
        mode: process.env.EAS_BUILD_PROFILE === "development" ? "development" : "production",
      }],
      [
        "react-native-maps",
        {
          androidGoogleMapsApiKey: googleMapsApiKey,
          iosGoogleMapsApiKey: googleMapsApiKey,
        },
      ],
    ],
  };
};
