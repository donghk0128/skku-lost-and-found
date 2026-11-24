import { initializePushBackground } from "./src/lib/push-client";

initializePushBackground();
// The router entry must run after background message registration.
require("expo-router/entry");
