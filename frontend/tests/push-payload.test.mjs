import assert from "node:assert/strict";
import test from "node:test";
import { parsePostPush } from "../src/lib/push-payload.ts";

const id = "49c83416-7967-4f86-a718-1d609f231358";
test("only validated post notifications can navigate", () => {
  const payload = { type: "keyword_post", post_id: id, user_id: id, notification_id: id };
  assert.deepEqual(parsePostPush(payload), payload);
  assert.equal(parsePostPush({ ...payload, post_id: "https://example.com" }), null);
  assert.equal(parsePostPush({ ...payload, user_id: undefined }), null);
  assert.equal(parsePostPush({ ...payload, notification_id: "../settings" }), null);
  assert.equal(parsePostPush({ ...payload, type: "other" }), null);
  assert.equal(parsePostPush(null), null);
});
