const { withAndroidManifest } = require("expo/config-plugins");

// Keep the app's FCM defaults when merging React Native Firebase's library manifest.
const overrides = {
  "com.google.firebase.messaging.default_notification_channel_id": "android:value",
  "com.google.firebase.messaging.default_notification_color": "android:resource",
};

module.exports = (config) => withAndroidManifest(config, (config) => {
  const manifest = config.modResults.manifest;
  manifest.$["xmlns:tools"] = "http://schemas.android.com/tools";

  const metadata = manifest.application?.[0]?.["meta-data"] ?? [];
  for (const [name, attribute] of Object.entries(overrides)) {
    const entry = metadata.find((item) => item.$["android:name"] === name);
    if (!entry) throw new Error(`Missing notification metadata: ${name}`);
    entry.$["tools:replace"] = attribute;
  }

  return config;
});
