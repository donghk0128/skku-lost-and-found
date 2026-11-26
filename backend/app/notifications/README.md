# Keyword push notifications

## Chat message notifications

Migration `0019_chat_push_notifications` adds a separate transactional outbox for
chat messages. Text, image, HTTP and WebSocket sends all use the same chat service;
only a newly committed message creates push work for the other participant's
currently registered devices. A retry with the same `client_message_id` does not
create another push. The existing device-wide notification switch controls chat
push as well. Per-room switches are not part of this change.

Before sending, the worker cancels work for a read message, a superseded message
in the same room, a closed room, an expired or revoked session, or a reassigned
device. Text previews are capped at 200 characters; an image without a caption
uses a photo placeholder. Android chat sends are high-priority data-only messages,
so FCM does not collapse different rooms before delivery; the background handler
displays a local notification and replaces the previous preview for that room.
On iOS, APNs alerts use a per-room collapse ID. Taps open the room and fetch its
current history from the server. FCM/APNs can reorder or drop delivery, and
Android can discard a large offline backlog, so a terminated app cannot guarantee
that the tray preview always matches the server's newest message at every instant.

Apply migrations through `0019_chat_push_notifications` before deploying an API
or worker with chat push enabled. Existing Firebase credentials, `PUSH_ENABLED`,
push worker and device registration are reused. When both kinds of work are
queued, the worker alternates between them.

Saved conditions opt in individually (`notification_enabled`, default `false`).
Only posts **created after enabling** are evaluated. Editing an existing post,
saving a condition, re-enabling it, or registering a new device does not backfill.
The worker also cancels pending work after condition deletion/disable, logout,
device reassignment, post deletion/completion, or expiry.

The post transaction writes an outbox with recipients and matching condition IDs.
It shares the browsing SQL predicates (AND between fields, OR within each field,
all location texts, literal phrases). The worker sends only committed jobs.
Unique constraints deduplicate account/post and notification/device pairs.
Each currently registered device can receive one notification.

## Client and Firebase setup

The client uses React Native Firebase 27's **Firebase Installation ID (FID)**
registration (`register` / `onRegistered`). The backend uses Firebase Admin 7.5+
`Message(fid=...)`, sending directly through FCM for Android and iOS. This does
not use Expo Push Service or Expo push tokens. Expo/EAS is used for native builds.

- Android: `frontend/google-services.json`, package `com.skku.finder`.
  The original file was registered for `com.jessi026.frontend`; replace it with
  the configuration downloaded for the new package in the team's Firebase project.
- iOS: register bundle identifier `com.skku.finder` in the same Firebase project,
  obtain `GoogleService-Info.plist`, and upload the Apple team's APNs authentication
  key to Firebase Cloud Messaging. iOS signing and the push capability must be enabled.
- `frontend/app.config.js` reads `GOOGLE_SERVICES_ANDROID` / `GOOGLE_SERVICES_IOS`
  when files are supplied through EAS file environment variables. Otherwise it
  uses the files above in `frontend`. Do not put the Admin service account in the app.
- `app.json` already links the team's EAS project. Keep that project ID and the
  team's `eas.json` profiles (remote app versions and production auto-increment).
  `EAS_PROJECT_ID` and `EAS_PROJECT_OWNER` are optional overrides; normally leave
  them empty. Do not create another EAS project.
- Build using `npx.cmd eas-cli@latest build --platform android --profile development`
  (or `--platform ios`). This requires the responsible account/build permissions.
  Expo Go and web do not receive this app's native remote notifications.
- React Native Firebase 27 requires iOS dynamic frameworks/SPM. The config uses
  `expo-build-properties` `useFrameworks: dynamic`; do not change it to static.
- Set the device-reachable `EXPO_PUBLIC_API_URL` for physical-device builds.
  A phone cannot use the developer computer's `localhost`.

The account screen's existing **알림 받기** toggle is the device-wide preference
(same `lost-found-notifications` storage key). Turning it off detaches this device
from the server, unregisters FCM and clears its notification tray without changing
account-owned condition switches. Startup, foregrounding and registration refresh
respect both this preference and OS permission. Enabling an individual condition
on mobile requests permission and also enables this device preference; the
account toggle refreshes to show the new state.

On mobile, enabling a condition registers the device with a proven live login
session. Permission refusal preserves the condition as disabled. Foreground
messages show a local banner, OS notifications
cover background/terminated states, and taps open `/post/[id]` only when the
recipient matches the signed-in account. Web can manage conditions but needs a
permission-enabled mobile installation to receive them.

## Server setup

1. Apply `0016_push_notifications`: `docker compose run --rm backend alembic upgrade head`.
2. Place the server service account at **repository root** `.deps/firebase-admin.json`.
   `.deps/` must remain gitignored. Never commit/share it in the application bundle.
3. In `backend/.env`, set `PUSH_ENABLED=true`. Optionally set `FIREBASE_PROJECT_ID`
   to the same project's ID. Restart the backend so new posts enqueue work.
4. Start `docker compose --profile push up -d --build push-worker`.
   The worker mounts `.deps` read-only at `/run/firebase`; the API does not need
   access to the key. Apply migrations before starting the worker.
5. For a local Python worker launched from `backend`, set
   `FIREBASE_CREDENTIALS_PATH=../.deps/firebase-admin.json` and run
   `python -m app.notifications.worker`. ADC is supported when the path is empty.

Production compose also has an opt-in `push` profile; set the production DB URL
and mount the production service account separately. Push remains **off by default**.
No real notification or Firebase network request is required by the tests.

## Delivery and validation

Workers use PostgreSQL `FOR UPDATE SKIP LOCKED`. Transient failures retry with
exponential backoff (60 seconds initially, at most 6 attempts by default).
Unregistered installations are disabled. Pending work expires after 24 hours.
FCM acceptance means accepted for transport, not proven receipt by the phone.
Network ambiguity or a crash after FCM accepts but before DB commit can cause
another attempt: external delivery cannot guarantee exactly-once behavior.
Stable Android notification tags and APNs collapse IDs reduce duplicate display.
Messages already handed to FCM/OS cannot be retracted by a subsequent logout.

Before enabling real sending, validate on Android and iPhone development builds:

- Allow/deny/revoke permission, registration renewal, logout and account switching.
- A matching **new** post alerts; old/self/nonmatching/edited posts do not.
- Multiple matching conditions produce one alert per device.
- Disable/delete before delivery cancels it; another still-enabled matching condition keeps it.
- Foreground/background/terminated receipt and tap-to-post navigation.
- Deleted posts show the existing not-found flow when an older alert is tapped.

References: [React Native Firebase messaging](https://rnfirebase.io/messaging/usage),
[Expo SDK 57 notifications](https://docs.expo.dev/versions/v57.0.0/sdk/notifications/),
[Firebase Admin sending](https://firebase.google.com/docs/cloud-messaging/send/admin-sdk).
