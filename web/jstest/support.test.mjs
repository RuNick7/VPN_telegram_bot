import { test } from "node:test";
import assert from "node:assert/strict";

import {
  ACCEPT,
  LIMITS,
  checkFiles,
  formatSize,
  kindOf,
  statusView,
  ticketFromSearch,
} from "../frontend/assets/js/support-files.js";

const MB = 1024 * 1024;
const file = (name, type, size = 1000) => ({ name, type, size });

test("each accepted kind is recognised by its type", () => {
  assert.equal(kindOf(file("a.jpg", "image/jpeg")), "image");
  assert.equal(kindOf(file("a.mov", "video/quicktime")), "video");
  assert.equal(kindOf(file("a.webm", "video/webm")), "video");
  assert.equal(kindOf(file("a.pdf", "application/pdf")), "document");
  assert.equal(kindOf(file("a.txt", "text/plain")), "document");
});

test("a file the browser could not type is judged by its name", () => {
  assert.equal(kindOf(file("app.log", "")), "document");
  assert.equal(kindOf(file("clip.MP4", "")), "video");
  assert.equal(kindOf(file("setup.exe", "")), "");
});

test("a type the browser did name is not overruled by a friendlier name", () => {
  // An iPhone photo renamed to .jpg is still HEIC, and the server would
  // refuse it after the upload rather than before.
  assert.equal(kindOf(file("photo.jpg", "image/heic")), "");
  assert.equal(kindOf(file("archive.pdf", "application/zip")), "");
});

test("a sensible selection passes", () => {
  assert.equal(
    checkFiles([file("a.png", "image/png"), file("b.mp4", "video/mp4", 30 * MB)]),
    null
  );
});

test("each kind is held to its own limit", () => {
  assert.match(checkFiles([file("big.jpg", "image/jpeg", LIMITS.image + 1)]), /больше 10 МБ/);
  assert.equal(checkFiles([file("ok.mp4", "video/mp4", LIMITS.image + 1)]), null);
  assert.match(checkFiles([file("huge.mov", "video/quicktime", LIMITS.video + 1)]), /больше 45 МБ/);
});

test("the count, the total and empty files are refused with a reason", () => {
  const four = Array.from({ length: 4 }, (_, i) => file(`${i}.png`, "image/png"));
  assert.match(checkFiles(four), /не больше 3 файлов/);

  const heavy = [file("a.mp4", "video/mp4", 30 * MB), file("b.mp4", "video/mp4", 30 * MB)];
  assert.match(checkFiles(heavy), /вместе — не больше 50 МБ/);

  assert.match(checkFiles([file("empty.txt", "text/plain", 0)]), /пустой/);
});

test("the refusal names the file and says what would do", () => {
  const message = checkFiles([file("virus.exe", "application/x-msdownload")]);
  assert.match(message, /virus\.exe/);
  assert.match(message, /MP4, MOV, WebM/);
});

test("the file picker offers exactly the accepted kinds", () => {
  for (const entry of ["image/jpeg", "video/quicktime", "application/pdf", ".log", ".mov"]) {
    assert.ok(ACCEPT.split(",").includes(entry), `${entry} missing from accept`);
  }
  assert.ok(!ACCEPT.includes("heic"));
});

test("sizes read the way people say them", () => {
  assert.equal(formatSize(300), "1 КБ");
  assert.equal(formatSize(340 * 1024), "340 КБ");
  assert.equal(formatSize(1.5 * MB), "1,5 МБ");
  assert.equal(formatSize(2 * MB), "2 МБ");
  assert.equal(formatSize(44.6 * MB), "45 МБ");
});

test("every status has a label", () => {
  assert.equal(statusView("open").label, "На рассмотрении");
  assert.equal(statusView("answered").label, "Есть ответ");
  assert.equal(statusView("closed").kind, "off");
});

test("only a plain positive number is taken as a ticket id", () => {
  assert.equal(ticketFromSearch("?id=42"), "42");
  assert.equal(ticketFromSearch("?id=0"), null);
  assert.equal(ticketFromSearch("?id=42abc"), null);
  assert.equal(ticketFromSearch("?id=../../api"), null);
  assert.equal(ticketFromSearch(""), null);
});
