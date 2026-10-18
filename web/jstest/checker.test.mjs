/*
 * Tests for the download page of «KairaVPN Проверка» (/check).
 *
 * The files are built in vpncheck/ and published by its own repository, so a
 * renamed file there would leave this page linking to a 404 with nothing
 * failing. These pin the names against the build, and the page's static list
 * against the table its button is picked from.
 *
 * Run: node --test web/jstest/*.test.mjs
 */

import test from "node:test";
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const { FILES, RELEASES, pickFile } = await import("../frontend/assets/js/checker.js");

const read = (path) => readFileSync(new URL(path, import.meta.url), "utf8");

test("every file is one vpncheck builds", () => {
  const builds = read("../../vpncheck/build.sh") + read("../../vpncheck/packaging/macos.sh");
  for (const file of FILES) {
    assert.ok(builds.includes(file.name), `${file.name} is not built by vpncheck`);
    assert.equal(file.href, RELEASES + "/download/" + file.name);
  }
});

test("the page lists every file, for a visitor with no script", () => {
  const page = read("../frontend/check.html");
  for (const file of FILES) {
    assert.ok(page.includes(`href="${file.href}"`), `check.html does not link ${file.name}`);
  }
});

test("the big button offers the visitor's own system", () => {
  const pick = (...args) => pickFile(...args)?.name ?? pickFile(...args);
  assert.equal(pick("Mozilla/5.0 (Windows NT 10.0; Win64; x64)"), "KairaVPN-Check-x64.exe");
  assert.equal(pick("Mozilla/5.0 (Windows NT 10.0; Win64; x64)", "arm"), "KairaVPN-Check-arm64.exe");
  assert.equal(pick("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)"), "KairaVPN-Check.dmg");
  assert.equal(pick("Mozilla/5.0 (X11; Linux x86_64)"), "KairaVPN-Check-linux-x64");
  assert.equal(pick("Mozilla/5.0 (X11; Linux aarch64)"), "KairaVPN-Check-linux-arm64");
});

test("a phone or tablet is told to use a computer", () => {
  assert.equal(pickFile("Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X)"), "phone");
  assert.equal(pickFile("Mozilla/5.0 (Linux; Android 14; Pixel 8)"), "phone");
  // iPadOS asks for the desktop site as a Mac; only its touch screen tells.
  assert.equal(pickFile("Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7)", "", 5), "phone");
});

test("an unknown system gets the list rather than a guess", () => {
  assert.equal(pickFile(""), null);
  assert.equal(pickFile("Mozilla/5.0 (X11; CrOS x86_64 14541.0.0)"), null);
});
