/*
 * Tests for the QR encoder.
 *
 * A wrong QR code looks exactly like a right one, so "it rendered" proves
 * nothing. The checks below anchor each stage to something outside this
 * repository: the Reed-Solomon example worked through in ISO/IEC 18004
 * Annex I, and the published format/version bit tables. The last test reads
 * the finished matrix back and compares it to what went in, which is what
 * catches a zigzag or masking mistake.
 *
 * Run: node --test web/jstest/
 */

import test from "node:test";
import assert from "node:assert/strict";

// The module builds SVG elements on demand only, so importing it outside a
// browser is fine as long as no test calls toSVG().
const qr = await import("../frontend/assets/js/qr.js");

test("Reed-Solomon matches the worked example in the standard", () => {
  // ISO/IEC 18004 Annex I: "01234567" as version 1, level M.
  const data = [16, 32, 12, 86, 97, 128, 236, 17, 236, 17, 236, 17, 236, 17, 236, 17];
  const expected = [165, 36, 212, 193, 237, 54, 199, 135, 44, 85];
  assert.deepEqual(qr.reedSolomon(data, 10), expected);
});

test("format bits match the published table for level M", () => {
  const table = [0x5412, 0x5125, 0x5e7c, 0x5b4b, 0x45f9, 0x40ce, 0x4f97, 0x4aa0];
  for (let mask = 0; mask < 8; mask += 1) {
    assert.equal(qr.formatBits(mask), table[mask], `mask ${mask}`);
  }
});

test("version bits match the published table", () => {
  const table = {
    7: 0x07c94, 8: 0x085bc, 9: 0x09a99,
    10: 0x0a4d3, 11: 0x0bbf6, 12: 0x0c762,
  };
  for (const [version, bits] of Object.entries(table)) {
    assert.equal(qr.versionBits(Number(version)), bits, `version ${version}`);
  }
});

test("the matrix has the fixed patterns every scanner looks for", () => {
  const m = qr.encode("https://kaira.example/sub/abc123");
  const size = m.length;

  assert.equal(size % 4, 1, "size must be 4v+17");
  assert.equal(m[0].length, size, "matrix must be square");

  // Finder: a 7x7 ring with a 3x3 core, at three corners.
  for (const [oy, ox] of [[0, 0], [0, size - 7], [size - 7, 0]]) {
    for (const [dy, dx, want] of [
      [0, 0, 1], [0, 3, 1], [3, 0, 1], [6, 6, 1],
      [1, 1, 0], [1, 5, 0], [5, 1, 0],
      [3, 3, 1], [2, 2, 1], [4, 4, 1],
    ]) {
      assert.equal(m[oy + dy][ox + dx], want, `finder at ${oy},${ox} offset ${dy},${dx}`);
    }
  }

  // Timing patterns alternate, starting dark at index 8.
  for (let i = 8; i < size - 8; i += 1) {
    assert.equal(m[6][i], i % 2 === 0 ? 1 : 0, `horizontal timing at ${i}`);
    assert.equal(m[i][6], i % 2 === 0 ? 1 : 0, `vertical timing at ${i}`);
  }

  assert.equal(m[size - 8][8], 1, "the always-dark module must be dark");
});

test("the format area decodes back to a real level-M format string", () => {
  const m = qr.encode("test");
  const size = m.length;

  let bits = 0;
  for (let i = 0; i <= 5; i += 1) bits |= m[8][i] << i;
  bits |= m[8][7] << 6;
  bits |= m[8][8] << 7;
  bits |= m[7][8] << 8;
  for (let i = 9; i <= 14; i += 1) bits |= m[14 - i][8] << i;

  const known = [0x5412, 0x5125, 0x5e7c, 0x5b4b, 0x45f9, 0x40ce, 0x4f97, 0x4aa0];
  assert.ok(known.includes(bits), `0x${bits.toString(16)} is not a level-M format string`);

  // The copy near the bottom-left / top-right must agree with it. Read 7 + 8,
  // stepping over the always-dark module at (size-8, 8).
  let mirror = 0;
  for (let i = 0; i <= 6; i += 1) mirror |= m[size - 1 - i][8] << i;
  for (let i = 7; i <= 14; i += 1) mirror |= m[8][size - 15 + i] << i;
  assert.equal(mirror, bits, "the two format copies disagree");
});

test("short and long payloads pick different versions and both stay valid", () => {
  const small = qr.encode("a");
  assert.equal(small.length, 21, "one byte should fit version 1");

  const long = qr.encode("x".repeat(200));
  assert.ok(long.length > 21, "200 bytes needs more than version 1");
  assert.equal(long.length % 4, 1);
});

test("a payload past version 12 is refused rather than silently truncated", () => {
  assert.throws(() => qr.encode("x".repeat(400)), /длинная/);
});

/**
 * Reads the payload back out of a finished matrix.
 *
 * Deliberately walks the zigzag itself rather than reusing the writer, so a
 * mistake in the traversal shows up as a garbled string instead of cancelling
 * out. Only the first block's header is parsed, which is all that is needed to
 * recover a short message that fits one block.
 */
function readBack(modules) {
  const size = modules.length;
  const version = (size - 17) / 4;
  const reserved = qr.reservedMask(size, version);

  const known = [0x5412, 0x5125, 0x5e7c, 0x5b4b, 0x45f9, 0x40ce, 0x4f97, 0x4aa0];
  let format = 0;
  for (let i = 0; i <= 5; i += 1) format |= modules[8][i] << i;
  format |= modules[8][7] << 6;
  format |= modules[8][8] << 7;
  format |= modules[7][8] << 8;
  for (let i = 9; i <= 14; i += 1) format |= modules[14 - i][8] << i;
  const mask = known.indexOf(format);
  assert.ok(mask >= 0, "unreadable format string");

  const masks = [
    (r, c) => (r + c) % 2 === 0,
    (r) => r % 2 === 0,
    (r, c) => c % 3 === 0,
    (r, c) => (r + c) % 3 === 0,
    (r, c) => (Math.floor(r / 2) + Math.floor(c / 3)) % 2 === 0,
    (r, c) => ((r * c) % 2) + ((r * c) % 3) === 0,
    (r, c) => (((r * c) % 2) + ((r * c) % 3)) % 2 === 0,
    (r, c) => (((r + c) % 2) + ((r * c) % 3)) % 2 === 0,
  ];

  const bits = [];
  let upward = true;
  for (let right = size - 1; right > 0; right -= 2) {
    if (right === 6) right = 5;
    for (let step = 0; step < size; step += 1) {
      const y = upward ? size - 1 - step : step;
      for (const x of [right, right - 1]) {
        if (reserved[y][x]) continue;
        bits.push(modules[y][x] ^ (masks[mask](y, x) ? 1 : 0));
      }
    }
    upward = !upward;
  }

  const take = (n) => bits.splice(0, n).reduce((acc, bit) => (acc << 1) | bit, 0);
  assert.equal(take(4), 0b0100, "mode indicator should say byte mode");
  const length = take(version < 10 ? 8 : 16);
  return { length, first: take(8) };
}

test("data placement round-trips: what is written can be read back", () => {
  // One block only (version 1–4 at level M has a single block), so the stream
  // is not interleaved and the header sits at the front of it.
  for (const text of ["a", "kaira", "https://sub.example/x1"]) {
    const decoded = readBack(qr.encode(text));
    const expected = new TextEncoder().encode(text);
    assert.equal(decoded.length, expected.length, `length for "${text}"`);
    assert.equal(decoded.first, expected[0], `first byte of "${text}"`);
  }
});

test("toSVG builds a scannable document", () => {
  // A minimum viable DOM: toSVG only ever calls createElementNS, setAttribute
  // and append, so standing those up is cheaper than a headless browser and
  // catches the thing that actually breaks here -- a misspelled attribute.
  const made = [];
  globalThis.document = {
    createElementNS(ns, tag) {
      const node = {
        ns,
        tag,
        attrs: {},
        children: [],
        textContent: "",
        setAttribute(k, v) {
          this.attrs[k] = v;
        },
        append(...kids) {
          this.children.push(...kids);
        },
      };
      made.push(node);
      return node;
    },
  };

  try {
    const svg = qr.toSVG("https://kairavpn.pro/sub/abc", { title: "тест" });

    assert.equal(svg.tag, "svg");
    assert.equal(svg.ns, "http://www.w3.org/2000/svg", "the SVG namespace is required");
    assert.match(svg.attrs.viewBox, /^0 0 \d+ \d+$/);

    // Four modules of quiet zone on each side, or many scanners see nothing.
    const [, , width] = svg.attrs.viewBox.split(" ").map(Number);
    const modules = qr.encode("https://kairavpn.pro/sub/abc").length;
    assert.equal(width, modules + 8, "quiet zone should be 4 modules a side");

    assert.equal(svg.attrs["shape-rendering"], "crispEdges", "anti-aliasing blurs the modules");

    const title = svg.children.find((c) => c.tag === "title");
    assert.equal(title?.textContent, "тест");

    // A light background under dark modules: inverted, a QR code is unreadable.
    const rect = svg.children.find((c) => c.tag === "rect");
    assert.ok(rect, "no background rect");
    assert.equal(rect.attrs.fill, "#f5f5f5");

    const path = svg.children.find((c) => c.tag === "path");
    assert.ok(path, "no path");
    assert.equal(path.attrs.fill, "#000");
    assert.ok(path.attrs.d.startsWith("M"), "path data should start with a move");
    assert.ok(path.attrs.d.length > 500, "suspiciously few modules drawn");
  } finally {
    delete globalThis.document;
  }
});

test("byte mode is 8-bit clean", () => {
  // Cyrillic is two UTF-8 bytes per character; a subscription URL will not
  // contain any, but truncating at the wrong boundary would be silent.
  assert.doesNotThrow(() => qr.encode("Проверка кириллицы в QR"));
});
