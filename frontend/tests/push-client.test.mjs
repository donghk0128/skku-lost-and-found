import assert from "node:assert/strict";
import test from "node:test";
import { runtime, deferred, flush, ownerId, postId, notificationId, installationId, preferenceKey } from "./helpers/push-runtime.mjs";

test("stored device OFF detaches registration without prompting or registering", async () => {
  const { state, client } = runtime();
  state.store.set(preferenceKey, "off");
  await client.syncPush();
  assert.equal(state.registrations, 0);
  assert.equal(state.prompts, 0);
  assert.equal(state.unregistrations, 1);
  assert.equal(state.requests[0].method, "DELETE");
  assert.equal(state.requests[0].path, `/users/me/push-devices/${installationId}`);
});

test("stored device ON registers FID with a live app session without another permission prompt", async () => {
  const { state, client } = runtime();
  state.store.set(preferenceKey, "on");
  await client.syncPush(); await flush();
  assert.equal(state.registrations, 1);
  assert.equal(state.prompts, 0);
  assert.ok(state.requests.length > 0);
  for (const request of state.requests) {
    assert.equal(request.body.fid, state.fid);
    assert.equal(request.body.installation_id, installationId);
    assert.equal(request.body.refresh_token, "refresh-a");
  }
});

test("enabling a condition also persists and announces the existing device preference", async () => {
  const { state, client, preference } = runtime();
  let changes = 0;
  const stop = preference.onNotificationPreferenceChange(() => { changes++; });
  assert.equal(await client.enablePush(), "granted");
  await flush(); stop();
  assert.equal(state.store.get(preferenceKey), "on");
  assert.equal(changes, 1);
  assert.equal(state.prompts, 1);
  assert.ok(state.requests.some(request => request.method === "POST"));
});

test("permission refusal never enables the device or sends its registration", async () => {
  const { state, client } = runtime();
  state.permission = { granted: false, canAskAgain: false };
  state.store.set(preferenceKey, "off");
  assert.equal(await client.enablePush(), "denied");
  assert.equal(state.store.get(preferenceKey), "off");
  assert.equal(state.registrations, 0);
  assert.equal(state.requests.length, 0);
});

test("turning OFF during an upload finishes with detachment and cannot be undone by a queued callback", async () => {
  const { state, client, preference } = runtime();
  state.store.set(preferenceKey, "on");
  const entered = deferred(), release = deferred();
  let blocked = false;
  state.onRequest = async request => {
    if (request.method === "POST" && !blocked) { blocked = true; entered.resolve(); await release.promise; }
  };
  const uploading = client.syncPush();
  await entered.promise;
  await preference.writeNotificationPreference(false);
  const disabling = client.syncPush();
  release.resolve();
  await uploading; await disabling; await flush();
  assert.equal(state.requests.at(-1).method, "DELETE");
  assert.equal(state.unregistrations, 1);
  assert.equal(state.store.get(preferenceKey), "off");
});

test("OS permission revocation detaches the device while preserving the user's stored preference", async () => {
  const { state, client } = runtime();
  state.store.set(preferenceKey, "on");
  state.permission = { granted: false, canAskAgain: false };
  await client.syncPush();
  assert.equal(state.requests.at(-1).method, "DELETE");
  assert.equal(state.registrations, 0);
  assert.equal(state.store.get(preferenceKey), "on");
});

test("an access-token refresh cannot overwrite a newly switched account", async () => {
  const { state, client, ApiError } = runtime();
  state.store.set(preferenceKey, "on");
  state.onRequest = async () => { throw new ApiError(401); };
  state.onRefresh = async () => {
    state.session = { access_token: "access-b", refresh_token: "refresh-b" };
    return { access_token: "refreshed-a" };
  };
  await client.syncPush();
  // The first upload is abandoned after detecting the account change.
  assert.equal(state.session.access_token, "access-b");
  assert.ok(state.requests.every(request => request.accessToken !== "refreshed-a"));
  await flush();
});

test("foreground receipt and taps respect recipient, master preference and deduplication", async () => {
  const { state, client, preference } = runtime();
  state.store.set(preferenceKey, "on");
  const stop = client.observePush(ownerId, id => state.opened.push(id));
  await flush();
  const data = { type: "keyword_post", user_id: ownerId, post_id: postId, notification_id: notificationId };
  const message = { data, notification: { title: "New post", body: "Item" } };
  await state.message({ ...message, data: { ...data, user_id: postId } });
  assert.equal(state.displayed.length, 0);
  await state.message(message); await state.message(message);
  assert.equal(state.displayed.length, 1);
  const remote = { request: { content: { data }, trigger: { type: "push" } } };
  const local = { request: { content: { data }, trigger: null } };
  assert.equal((await state.handler.handleNotification(remote)).shouldShowBanner, false);
  assert.equal((await state.handler.handleNotification(local)).shouldShowBanner, true);
  state.openedMessage(message);
  state.response({ notification: local });
  assert.deepEqual(state.opened, [postId]);
  await preference.writeNotificationPreference(false);
  assert.equal((await state.handler.handleNotification(local)).shouldShowBanner, false);
  stop();
});

test("chat push replaces the room preview and ignores an older arrival", async () => {
  const { state, client } = runtime();
  state.store.set(preferenceKey, "on");
  const stop = client.observePush(ownerId, id => state.opened.push(id), id => state.opened.push(id));
  await flush();
  const chat = sequence => ({
    data: { type: "chat_message", room_id: postId, user_id: ownerId,
      notification_id: sequence === 2 ? notificationId : installationId, sequence: String(sequence) },
    notification: { title: "상대방", body: `메시지 ${sequence}` },
  });
  await state.message(chat(1));
  await state.message(chat(2));
  await state.message(chat(1));
  assert.equal(state.displayed.length, 1);
  assert.equal(state.displayed[0].identifier, `chat-${postId}`);
  assert.equal(state.displayed[0].content.body, "메시지 2");
  state.openedMessage(chat(2));
  assert.deepEqual(state.opened, [postId]);
  stop();
});

test("Android background data pushes keep separate rooms and replace each room's preview", async () => {
  const { state, client } = runtime();
  state.store.set(preferenceKey, "on");
  state.store.set("push-recipient-id", ownerId);
  client.initializePushBackground();
  const chat = (room, sequence, id) => ({ data: {
    type: "chat_message", room_id: room, user_id: ownerId,
    notification_id: id, sequence: String(sequence), title: "상대방", body: `메시지 ${sequence}`,
  } });
  await state.background(chat(postId, 1, notificationId));
  await state.background(chat(installationId, 1, postId));
  await state.background(chat(postId, 2, installationId));
  assert.equal(state.displayed.length, 2);
  assert.equal(state.displayed.find(item => item.identifier === `chat-${postId}`).content.body, "메시지 2");
  assert.equal(state.displayed.find(item => item.identifier === `chat-${installationId}`).content.body, "메시지 1");
  assert.equal((await state.handler.handleNotification({ request: { content: state.displayed[0].content } })).shouldShowBanner, true);
  await client.clearPush();
  assert.equal((await state.handler.handleNotification({ request: { content: state.displayed[0].content } })).shouldShowBanner, false);
});
