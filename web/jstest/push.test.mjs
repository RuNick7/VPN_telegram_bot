import { test } from "node:test";
import assert from "node:assert/strict";

import { keyBytes, pushSupport } from "../frontend/assets/js/push.js";

test("keyBytes decodes the server's base64url key without padding", () => {
  // 65 bytes, as a P-256 public key is: 0x04 then X and Y.
  const raw = Uint8Array.from({ length: 65 }, (_, i) => (i * 37) & 0xff);
  raw[0] = 4;
  const encoded = Buffer.from(raw).toString("base64url");
  assert.ok(!encoded.includes("="));
  assert.deepEqual(keyBytes(encoded), raw);
});

const nav = (userAgent, extra = {}) => ({ userAgent, platform: "", maxTouchPoints: 0, ...extra });

test("pushSupport tells an iPhone outside the home screen to install", () => {
  const iphone = { navigator: nav("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)") };
  assert.equal(pushSupport(iphone), "ios-install");
  const ipad = { navigator: nav("Mozilla/5.0 (Macintosh)", { platform: "MacIntel", maxTouchPoints: 5 }) };
  assert.equal(pushSupport(ipad), "ios-install");
});

test("pushSupport is ok where all three APIs exist, and says so otherwise", () => {
  const full = { navigator: { ...nav("Chrome"), serviceWorker: {} }, PushManager: {}, Notification: {} };
  assert.equal(pushSupport(full), "ok");
  assert.equal(pushSupport({ navigator: nav("Old browser") }), "unsupported");
});
