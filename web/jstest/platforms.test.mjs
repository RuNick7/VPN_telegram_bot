/*
 * Tests for the per-device setup instructions.
 *
 * platforms.js is pure data, which is the point: an instruction that is
 * subtly wrong looks exactly like one that is right, and nobody notices until
 * a customer cannot connect. The bot's table is the reference — the site is
 * not allowed to offer a different set of platforms or a different app.
 *
 * Run: node --test web/jstest/
 */

import test from "node:test";
import assert from "node:assert/strict";

const { PLATFORMS, guessPlatform, importLink } = await import(
  "../frontend/assets/js/platforms.js"
);

const URL = "https://sub.kairavpn.pro/abc123";

/** Every string a step carries — visible text and href alike. */
function textOf(steps) {
  const parts = [];
  for (const step of steps) {
    parts.push(step.title);
    for (const part of step.body) {
      if (typeof part === "string") parts.push(part);
      else parts.push(part.text || "", part.code || "", part.open || "", part.href || "");
    }
  }
  return parts.join(" ");
}

test("the site offers exactly the platforms the bot does", () => {
  // user_bot/handlers/setup.py PLATFORMS. A device the bot can set up and the
  // site cannot is a customer told to go back to Telegram.
  assert.deepEqual(
    PLATFORMS.map((p) => p.key),
    ["android", "ios", "windows", "macos", "linux", "tv", "appletv"]
  );
});

test("every platform has steps and a fallback", () => {
  for (const platform of PLATFORMS) {
    const steps = platform.steps(URL);
    assert.ok(steps.length >= 3, `${platform.key} has too few steps`);
    for (const step of steps) {
      assert.ok(step.title, `${platform.key} has a step with no title`);
      assert.ok(step.body?.length, `${platform.key}: "${step.title}" has an empty body`);
    }
    assert.ok(platform.fallback(URL).length >= 1, `${platform.key} has no fallback`);
  }
});

test("a platform that declares it needs the link actually uses it", () => {
  for (const platform of PLATFORMS.filter((p) => p.needsURL)) {
    assert.match(
      textOf(platform.steps(URL)),
      new RegExp(URL.replace(/[.*+?^${}()|[\]\\]/g, "\\$&")),
      `${platform.key} claims to need the subscription URL but never shows it`
    );
  }
});

test("a platform that declares it does not need the link never leaks one", () => {
  // The TVs are paired from a phone. Rendering them with a link would put a
  // credential on screen for no reason, and they are rendered before one is
  // even known.
  for (const platform of PLATFORMS.filter((p) => !p.needsURL)) {
    assert.doesNotMatch(textOf(platform.steps("")), /undefined|null/);
    assert.doesNotMatch(textOf(platform.steps(URL)), new RegExp("abc123"));
  }
});

test("the import link carries the subscription URL and nothing else", () => {
  // Deliberately not the bot's vless-outline.ru wrapper: that exists to
  // survive Telegram's in-app browser, and using it here would hand a third
  // party every customer's subscription link for no gain.
  const link = importLink(URL);
  assert.ok(link.startsWith("happ://add/"));
  assert.ok(link.endsWith(URL));
  assert.doesNotMatch(link, /vless-outline/);
});

test("no step sends the subscription link through a third party", () => {
  for (const platform of PLATFORMS) {
    assert.doesNotMatch(
      textOf(platform.steps(URL)) + " " + textOf(platform.fallback(URL)),
      /vless-outline/,
      platform.key
    );
  }
});

test("no instruction points at an app we do not use", () => {
  for (const platform of PLATFORMS) {
    const text = textOf(platform.steps(URL)) + " " + textOf(platform.fallback(URL));
    assert.doesNotMatch(text, /v2ray|hiddify|streisand|foxray/i, `${platform.key}`);
  }
});

test("the default tab follows the user agent", () => {
  assert.equal(guessPlatform("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"), "ios");
  assert.equal(guessPlatform("Mozilla/5.0 (Linux; Android 14; Pixel 8)"), "android");
  assert.equal(guessPlatform("Mozilla/5.0 (Windows NT 10.0; Win64; x64)"), "windows");
  assert.equal(guessPlatform("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"), "macos");
  assert.equal(guessPlatform("Mozilla/5.0 (X11; Linux x86_64)"), "linux");
});

test("an Android phone is not mistaken for a Linux desktop", () => {
  // Android's user agent says "Linux" in it, so the order of those two checks
  // is the whole test: a phone sent to the NekoRay instructions gets eleven
  // steps it cannot follow.
  assert.equal(guessPlatform("Mozilla/5.0 (Linux; Android 14; SM-S911B) AppleWebKit/537.36"), "android");
});

test("an unrecognised agent still gets a usable tab", () => {
  assert.ok(PLATFORMS.some((p) => p.key === guessPlatform("")));
});
