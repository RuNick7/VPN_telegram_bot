/*
 * Tests for the pure helpers in core.js.
 *
 * core.js is the only frontend module with no side effects on import, which is
 * deliberate: it means the parts worth testing can be tested without a DOM.
 *
 * Run: node --test web/jstest/
 */

import test from "node:test";
import assert from "node:assert/strict";

const { promoCodeFrom, safePath, plural, daysLabel, formatTraffic } = await import(
  "../frontend/assets/js/core.js"
);

test("a bare promo code is normalised, not mangled", () => {
  assert.equal(promoCodeFrom("kaira-abc123"), "KAIRA-ABC123");
  assert.equal(promoCodeFrom("  GIFT9Z8Y7X  "), "GIFT9Z8Y7X");
});

test("a pasted gift link yields the code inside it", () => {
  // Both routes to the same single-use code: the link the site hands out and
  // the code the bot hands out have to resolve identically.
  assert.equal(promoCodeFrom("https://kairavpn.pro/gift/GIFT-ABC123"), "GIFT-ABC123");
  assert.equal(promoCodeFrom("/gift/GIFT-ABC123"), "GIFT-ABC123");
  assert.equal(promoCodeFrom("https://kairavpn.pro/gift/abc?utm=x"), "ABC");
  assert.equal(promoCodeFrom("kairavpn.pro/gift/xyz#top"), "XYZ");
});

test("a link with no code in it yields nothing rather than nonsense", () => {
  // Otherwise the gift page shows the customer "/GIFT/" as their code.
  assert.equal(promoCodeFrom("/gift/"), "");
  assert.equal(promoCodeFrom("https://kairavpn.pro/"), "");
  assert.equal(promoCodeFrom(""), "");
  assert.equal(promoCodeFrom(null), "");
});

test("percent-encoding in a gift link is decoded once", () => {
  assert.equal(promoCodeFrom("/gift/A%2DB"), "A-B");
  // A stray percent must not throw; the server rejects the code instead.
  assert.doesNotThrow(() => promoCodeFrom("/gift/100%off"));
});

test("safePath refuses anything that would leave this origin", () => {
  assert.equal(safePath("/app/plans"), "/app/plans");
  assert.equal(safePath("/app?x=1#y"), "/app?x=1#y");

  // Every one of these is a redirect off-site dressed as a path.
  assert.equal(safePath("//evil.example/x"), "/app");
  assert.equal(safePath("https://evil.example"), "/app");
  assert.equal(safePath("/\\evil.example"), "/app");
  assert.equal(safePath("app/plans"), "/app", "a relative path is not a path here");
  assert.equal(safePath(undefined), "/app");
  assert.equal(safePath(42), "/app");
});

test("safePath honours the caller's fallback", () => {
  assert.equal(safePath("//evil.example", "/login"), "/login");
});

test("Russian plurals pick the right form", () => {
  assert.equal(daysLabel(1), "1 день");
  assert.equal(daysLabel(2), "2 дня");
  assert.equal(daysLabel(5), "5 дней");
  assert.equal(daysLabel(11), "11 дней", "the teens are all the many-form");
  assert.equal(daysLabel(21), "21 день");
  assert.equal(daysLabel(22), "22 дня");
  assert.equal(daysLabel(111), "111 дней");
  assert.equal(daysLabel(0), "0 дней");
  assert.equal(plural(3, "человек", "человека", "человек"), "человека");
});

test("traffic reads the way a person would say it", () => {
  const GB = 1024 ** 3;
  const MB = 1024 ** 2;
  assert.equal(formatTraffic(0), "0 МБ");
  assert.equal(formatTraffic(-5), "0 МБ", "a negative balance is zero, not a minus sign");
  assert.equal(formatTraffic(GB), "1 ГБ");
  assert.equal(formatTraffic(1.5 * GB), "1.5 ГБ");
  assert.equal(formatTraffic(15 * GB), "15 ГБ");
  assert.equal(formatTraffic(350 * MB), "350 МБ");
});

test("a reading below a megabyte is shown, not rounded away", () => {
  // The point of the kilobyte branch: 123 КБ spent on a metered node has to
  // look different from nothing spent at all, or a working meter and a broken
  // one are indistinguishable on screen.
  assert.equal(formatTraffic(126406), "123 КБ");
  assert.equal(formatTraffic(1), "0 КБ", "still not zero megabytes");
});
