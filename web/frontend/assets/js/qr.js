/*
 * A QR encoder, byte mode, error-correction level M, versions 1–12.
 *
 * Written out rather than pulled from npm because the page's
 * Content-Security-Policy allows scripts from this origin and nowhere else,
 * and a CDN <script> is precisely the dependency this site should not have.
 * Twelve versions is 287 bytes of payload, several times the length of any
 * subscription URL the panel issues.
 *
 * Output is an <svg>: one path for every dark module, so it stays sharp when a
 * phone camera is held at whatever distance it likes, and costs no raster
 * asset.
 *
 * The tables below are from ISO/IEC 18004. `qr.test.mjs` checks the
 * Reed-Solomon stage against the worked example in the standard's Annex I and
 * the format bits against the published table, because a QR code that is
 * subtly wrong still looks exactly like a QR code.
 */

// [ec codewords per block, group1 blocks, group1 data cw, group2 blocks, group2 data cw]
const ECC_M = {
  1: [10, 1, 16, 0, 0],
  2: [16, 1, 28, 0, 0],
  3: [26, 1, 44, 0, 0],
  4: [18, 2, 32, 0, 0],
  5: [24, 2, 43, 0, 0],
  6: [16, 4, 27, 0, 0],
  7: [18, 4, 31, 0, 0],
  8: [22, 2, 38, 2, 39],
  9: [22, 3, 36, 2, 37],
  10: [26, 4, 43, 1, 44],
  11: [30, 1, 50, 4, 51],
  12: [22, 6, 36, 2, 37],
};

const ALIGN = {
  1: [], 2: [6, 18], 3: [6, 22], 4: [6, 26], 5: [6, 30], 6: [6, 34],
  7: [6, 22, 38], 8: [6, 24, 42], 9: [6, 26, 46], 10: [6, 28, 50],
  11: [6, 30, 54], 12: [6, 32, 58],
};

// -- GF(256), primitive polynomial 0x11D --------------------------------------

const EXP = new Uint8Array(512);
const LOG = new Uint8Array(256);
{
  let x = 1;
  for (let i = 0; i < 255; i += 1) {
    EXP[i] = x;
    LOG[x] = i;
    x <<= 1;
    if (x & 0x100) x ^= 0x11d;
  }
  for (let i = 255; i < 512; i += 1) EXP[i] = EXP[i - 255];
}

const mul = (a, b) => (a === 0 || b === 0 ? 0 : EXP[LOG[a] + LOG[b]]);

/** Generator polynomial for `degree` error-correction codewords. */
function generator(degree) {
  let poly = [1];
  for (let i = 0; i < degree; i += 1) {
    const next = new Array(poly.length + 1).fill(0);
    for (let j = 0; j < poly.length; j += 1) {
      next[j] ^= poly[j];
      next[j + 1] ^= mul(poly[j], EXP[i]);
    }
    poly = next;
  }
  return poly;
}

/** Remainder of `data` divided by the generator — the EC codewords. */
export function reedSolomon(data, ecCount) {
  const gen = generator(ecCount);
  const remainder = new Array(ecCount).fill(0);
  for (const byte of data) {
    const factor = byte ^ remainder[0];
    remainder.shift();
    remainder.push(0);
    for (let i = 0; i < ecCount; i += 1) {
      remainder[i] ^= mul(gen[i + 1], factor);
    }
  }
  return remainder;
}

// -- BCH ----------------------------------------------------------------------

function bch(value, generatorPoly, bits) {
  let result = value << bits;
  const genBits = 32 - Math.clz32(generatorPoly);
  while (32 - Math.clz32(result) >= genBits) {
    result ^= generatorPoly << (32 - Math.clz32(result) - genBits);
  }
  return (value << bits) | result;
}

/** 15-bit format information for level M and the given mask. */
export function formatBits(mask) {
  // 0b00 is level M; the five data bits are (level << 3) | mask.
  return bch(mask, 0x537, 10) ^ 0x5412;
}

/** 18-bit version information, only present from version 7 up. */
export function versionBits(version) {
  return bch(version, 0x1f25, 12);
}

// -- bit stream ---------------------------------------------------------------

function encodeData(bytes, version) {
  const [ecPerBlock, g1, g1cw, g2, g2cw] = ECC_M[version];
  const totalData = g1 * g1cw + g2 * g2cw;
  const countBits = version < 10 ? 8 : 16;

  const bits = [];
  const push = (value, length) => {
    for (let i = length - 1; i >= 0; i -= 1) bits.push((value >> i) & 1);
  };

  push(0b0100, 4); // byte mode
  push(bytes.length, countBits);
  for (const byte of bytes) push(byte, 8);

  // Terminator, then pad to a whole codeword, then the two alternating pad
  // bytes the standard specifies.
  const capacity = totalData * 8;
  push(0, Math.min(4, capacity - bits.length));
  while (bits.length % 8 !== 0) bits.push(0);

  const codewords = [];
  for (let i = 0; i < bits.length; i += 8) {
    codewords.push(bits.slice(i, i + 8).reduce((acc, bit) => (acc << 1) | bit, 0));
  }
  for (let i = 0; codewords.length < totalData; i += 1) {
    codewords.push(i % 2 === 0 ? 0xec : 0x11);
  }

  // Split into blocks, then interleave. Interleaving is what makes a burst of
  // damage land across many blocks instead of destroying one outright.
  const blocks = [];
  let offset = 0;
  for (const [count, size] of [[g1, g1cw], [g2, g2cw]]) {
    for (let i = 0; i < count; i += 1) {
      const data = codewords.slice(offset, offset + size);
      offset += size;
      blocks.push({ data, ec: reedSolomon(data, ecPerBlock) });
    }
  }

  const out = [];
  const longest = Math.max(...blocks.map((b) => b.data.length));
  for (let i = 0; i < longest; i += 1) {
    for (const block of blocks) if (i < block.data.length) out.push(block.data[i]);
  }
  for (let i = 0; i < ecPerBlock; i += 1) {
    for (const block of blocks) out.push(block.ec[i]);
  }
  return out;
}

/** Smallest version that fits `length` bytes at level M. */
function pickVersion(length) {
  for (const version of Object.keys(ECC_M).map(Number)) {
    const [, g1, g1cw, g2, g2cw] = ECC_M[version];
    const capacityBits = (g1 * g1cw + g2 * g2cw) * 8;
    const headerBits = 4 + (version < 10 ? 8 : 16);
    if (headerBits + length * 8 <= capacityBits) return version;
  }
  return null;
}

// -- matrix -------------------------------------------------------------------

function blankMatrix(size) {
  return {
    modules: Array.from({ length: size }, () => new Int8Array(size).fill(-1)),
    size,
  };
}

function placeFunctionPatterns(m, version) {
  const { modules, size } = m;
  const set = (x, y, value) => {
    if (x >= 0 && x < size && y >= 0 && y < size) modules[y][x] = value;
  };

  // Finders plus their separators.
  for (const [ox, oy] of [[0, 0], [size - 7, 0], [0, size - 7]]) {
    for (let y = -1; y <= 7; y += 1) {
      for (let x = -1; x <= 7; x += 1) {
        const onRing = x === 0 || x === 6 || y === 0 || y === 6;
        const inCore = x >= 2 && x <= 4 && y >= 2 && y <= 4;
        const inside = x >= 0 && x <= 6 && y >= 0 && y <= 6;
        set(ox + x, oy + y, inside && (onRing || inCore) ? 1 : 0);
      }
    }
  }

  // Timing.
  for (let i = 8; i < size - 8; i += 1) {
    const value = i % 2 === 0 ? 1 : 0;
    modules[6][i] = value;
    modules[i][6] = value;
  }

  // Alignment, skipping the three that would sit on a finder.
  const centres = ALIGN[version];
  for (const cy of centres) {
    for (const cx of centres) {
      const onFinder =
        (cx <= 8 && cy <= 8) || (cx <= 8 && cy >= size - 9) || (cx >= size - 9 && cy <= 8);
      if (onFinder) continue;
      for (let y = -2; y <= 2; y += 1) {
        for (let x = -2; x <= 2; x += 1) {
          const ring = Math.max(Math.abs(x), Math.abs(y));
          set(cx + x, cy + y, ring === 1 ? 0 : 1);
        }
      }
    }
  }

  modules[size - 8][8] = 1; // the always-dark module

  // Reserve the format areas so data placement skips them.
  for (let i = 0; i < 9; i += 1) {
    if (modules[8][i] === -1) modules[8][i] = 0;
    if (modules[i][8] === -1) modules[i][8] = 0;
  }
  for (let i = 0; i < 8; i += 1) {
    if (modules[8][size - 1 - i] === -1) modules[8][size - 1 - i] = 0;
    if (modules[size - 1 - i][8] === -1) modules[size - 1 - i][8] = 0;
  }

  if (version >= 7) {
    const bits = versionBits(version);
    for (let i = 0; i < 18; i += 1) {
      const bit = (bits >> i) & 1;
      modules[Math.floor(i / 3)][size - 11 + (i % 3)] = bit;
      modules[size - 11 + (i % 3)][Math.floor(i / 3)] = bit;
    }
  }
}

/**
 * Which cells the data stream may not write to.
 *
 * Exported for the round-trip test, which reads the finished matrix back and
 * needs to skip the same cells the writer did.
 */
export function reservedMask(size, version) {
  const probe = blankMatrix(size);
  placeFunctionPatterns(probe, version);
  return probe.modules.map((row) => row.map((cell) => cell !== -1));
}

function placeData(m, codewords, reserved) {
  const { modules, size } = m;
  let bitIndex = 0;
  const nextBit = () => {
    const byte = codewords[bitIndex >> 3];
    const bit = byte === undefined ? 0 : (byte >> (7 - (bitIndex & 7))) & 1;
    bitIndex += 1;
    return bit;
  };

  let upward = true;
  for (let right = size - 1; right > 0; right -= 2) {
    // Column 6 is the vertical timing pattern; the zigzag steps over it.
    if (right === 6) right = 5;
    for (let step = 0; step < size; step += 1) {
      const y = upward ? size - 1 - step : step;
      for (const x of [right, right - 1]) {
        if (reserved[y][x]) continue;
        modules[y][x] = nextBit();
      }
    }
    upward = !upward;
  }
}

const MASKS = [
  (r, c) => (r + c) % 2 === 0,
  (r) => r % 2 === 0,
  (r, c) => c % 3 === 0,
  (r, c) => (r + c) % 3 === 0,
  (r, c) => (Math.floor(r / 2) + Math.floor(c / 3)) % 2 === 0,
  (r, c) => ((r * c) % 2) + ((r * c) % 3) === 0,
  (r, c) => (((r * c) % 2) + ((r * c) % 3)) % 2 === 0,
  (r, c) => (((r + c) % 2) + ((r * c) % 3)) % 2 === 0,
];

function penalty(modules, size) {
  let score = 0;

  // Rule 1: runs of five or more.
  for (let i = 0; i < size; i += 1) {
    for (const line of [modules[i], modules.map((row) => row[i])]) {
      let run = 1;
      for (let j = 1; j < size; j += 1) {
        if (line[j] === line[j - 1]) {
          run += 1;
          if (run === 5) score += 3;
          else if (run > 5) score += 1;
        } else {
          run = 1;
        }
      }
    }
  }

  // Rule 2: solid 2x2 blocks.
  for (let y = 0; y < size - 1; y += 1) {
    for (let x = 0; x < size - 1; x += 1) {
      const v = modules[y][x];
      if (v === modules[y][x + 1] && v === modules[y + 1][x] && v === modules[y + 1][x + 1]) {
        score += 3;
      }
    }
  }

  // Rule 3: anything that looks like a finder.
  const a = [1, 0, 1, 1, 1, 0, 1, 0, 0, 0, 0];
  const b = [0, 0, 0, 0, 1, 0, 1, 1, 1, 0, 1];
  const matches = (line, at, pattern) => pattern.every((bit, k) => line[at + k] === bit);
  for (let i = 0; i < size; i += 1) {
    const row = Array.from(modules[i]);
    const col = modules.map((r) => r[i]);
    for (const line of [row, col]) {
      for (let j = 0; j + 11 <= size; j += 1) {
        if (matches(line, j, a) || matches(line, j, b)) score += 40;
      }
    }
  }

  // Rule 4: departure from an even split of dark and light.
  let dark = 0;
  for (let y = 0; y < size; y += 1) for (let x = 0; x < size; x += 1) dark += modules[y][x];
  const percent = (dark * 100) / (size * size);
  score += Math.floor(Math.abs(percent - 50) / 5) * 10;

  return score;
}

function applyFormat(modules, size, mask) {
  const bits = formatBits(mask);
  const bit = (i) => (bits >> i) & 1;

  // Copy 1, wrapped around the top-left finder.
  for (let i = 0; i <= 5; i += 1) modules[8][i] = bit(i);
  modules[8][7] = bit(6);
  modules[8][8] = bit(7);
  modules[7][8] = bit(8);
  for (let i = 9; i <= 14; i += 1) modules[14 - i][8] = bit(i);

  // Copy 2 is split 7 + 8, not 8 + 7: the eighth cell going up the left edge
  // is the always-dark module, which is not part of the format string.
  for (let i = 0; i <= 6; i += 1) modules[size - 1 - i][8] = bit(i);
  for (let i = 7; i <= 14; i += 1) modules[8][size - 15 + i] = bit(i);
}

/**
 * Encodes `text` and returns the module matrix as an array of Uint8Array rows.
 * Throws if the text is longer than version 12 at level M can hold.
 */
export function encode(text) {
  const bytes = new TextEncoder().encode(text);
  const version = pickVersion(bytes.length);
  if (version === null) throw new Error("QR: слишком длинная строка");

  const size = version * 4 + 17;
  const codewords = encodeData(bytes, version);
  const reserved = reservedMask(size, version);

  let best = null;
  for (let mask = 0; mask < 8; mask += 1) {
    const m = blankMatrix(size);
    placeFunctionPatterns(m, version);
    placeData(m, codewords, reserved);
    for (let y = 0; y < size; y += 1) {
      for (let x = 0; x < size; x += 1) {
        if (!reserved[y][x] && MASKS[mask](y, x)) m.modules[y][x] ^= 1;
      }
    }
    applyFormat(m.modules, size, mask);
    const score = penalty(m.modules, size);
    if (best === null || score < best.score) best = { score, modules: m.modules };
  }
  return best.modules;
}

/**
 * Renders `text` as an SVG element.
 *
 * The quiet zone is four modules on every side, which is not optional: without
 * it many scanners simply do not see the code.
 */
export function toSVG(text, { title = "QR-код" } = {}) {
  const modules = encode(text);
  const size = modules.length;
  const quiet = 4;
  const total = size + quiet * 2;

  // One path for all dark modules. Per-rect would be several times the bytes
  // and gives the renderer hairline seams between neighbours.
  let d = "";
  for (let y = 0; y < size; y += 1) {
    for (let x = 0; x < size; x += 1) {
      if (modules[y][x]) d += `M${x + quiet} ${y + quiet}h1v1h-1z`;
    }
  }

  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("viewBox", `0 0 ${total} ${total}`);
  svg.setAttribute("role", "img");
  svg.setAttribute("shape-rendering", "crispEdges");

  const label = document.createElementNS(ns, "title");
  label.textContent = title;
  svg.append(label);

  const background = document.createElementNS(ns, "rect");
  background.setAttribute("width", String(total));
  background.setAttribute("height", String(total));
  background.setAttribute("fill", "#f5f5f5");
  svg.append(background);

  const path = document.createElementNS(ns, "path");
  path.setAttribute("d", d);
  path.setAttribute("fill", "#000");
  svg.append(path);

  return svg;
}
