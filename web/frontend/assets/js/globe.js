/*
 * The cabinet's globe: a dotted Earth with the server locations lit on it.
 *
 * One full-screen fragment shader: every pixel is projected back onto a sphere
 * (orthographic), snapped to the nearest dot of a latitude-row grid, and lit
 * from the land mask and the sites. Site markers and labels are DOM on top,
 * placed through the CSSOM, so the page keeps its CSP without 'unsafe-inline'.
 *
 * On the first frames a scan wave spreads from the visitor's city and switches
 * the dots on; each server's marker rises in when the wave reaches it.
 * Skipped under prefers-reduced-motion. The landing page's planet
 * (planet.js) is a different picture and shares only the land mask.
 */

const DEG = Math.PI / 180;

const VERT = `
attribute vec2 aPos;
varying vec2 vUv;
void main() {
  vUv = aPos * 0.5 + 0.5;
  gl_Position = vec4(aPos, 0.0, 1.0);
}`;

const FRAG = `
precision highp float;
varying vec2 vUv;
uniform vec2 uRes;
uniform float uDpr;
uniform float uTime;
uniform float uMotion;
uniform sampler2D uLand;
uniform vec3 uGlobe;
uniform vec2 uView;
uniform float uStep;
uniform float uRise;
uniform float uSpin;
uniform float uAtmo;
uniform float uWave;
uniform float uFront;
uniform vec2 uOrigin;
uniform vec3 uViolet;
uniform vec3 uCoral;
uniform vec4 uFade;
uniform vec4 uSites[8];
uniform int uSiteCount;

const float DEG = 0.017453292;

float sq(float x) { return x * x; }

float near(vec2 a, vec2 b) {
  float dl = mod(a.x - b.x + 540.0, 360.0) - 180.0;
  return length(vec2(dl * cos(b.y * DEG), a.y - b.y));
}

float arc(vec2 a, vec2 b) {
  vec2 p = a * DEG;
  vec2 r = b * DEG;
  float c = sin(p.y) * sin(r.y) + cos(p.y) * cos(r.y) * cos(p.x - r.x);
  return acos(clamp(c, -1.0, 1.0)) / DEG;
}

float hash(vec2 p) { return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453); }

float noise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(mix(hash(i), hash(i + vec2(1.0, 0.0)), u.x),
             mix(hash(i + vec2(0.0, 1.0)), hash(i + vec2(1.0, 1.0)), u.x), u.y);
}

float land(vec2 g) {
  vec2 t = vec2(fract((g.x + 180.0) / 360.0), clamp((90.0 - g.y) / 180.0, 0.0, 1.0));
  return smoothstep(0.3, 0.7, texture2D(uLand, t).r);
}

float edgeFade() {
  return smoothstep(0.0, uFade.x, vUv.x) * smoothstep(0.0, uFade.y, 1.0 - vUv.x)
       * smoothstep(0.0, uFade.w, vUv.y) * smoothstep(0.0, uFade.z, 1.0 - vUv.y);
}

vec4 over(vec3 c, float a, vec3 uc, float ua) {
  float oa = a + ua * (1.0 - a);
  return vec4((c * a + uc * ua * (1.0 - a)) / max(oa, 0.0001), oa);
}

void main() {
  vec2 css = vec2(gl_FragCoord.x, uRes.y - gl_FragCoord.y) / uDpr;
  float R = uGlobe.z;
  vec2 q = (css - vec2(uGlobe.x, uGlobe.y + uRise)) / R;
  q.y = -q.y;
  float rr = length(q);
  float front = uWave * uFront;

  // Violet along the horizon, warming to coral on the right.
  vec3 atmoCol = mix(uViolet, uCoral, smoothstep(0.45, 1.0, vUv.x) * 0.85);
  float edge = (rr - 1.0) * R;
  float atmo = edge > 0.0
    ? exp(-edge / 24.0) * 0.55
    : exp(edge / 9.0) * 0.35 + exp(edge / 90.0) * 0.07;
  atmo *= 0.25 + 0.75 * uAtmo;

  if (rr >= 1.0) {
    float a0 = clamp(atmo * edgeFade(), 0.0, 1.0);
    gl_FragColor = vec4(atmoCol * a0, a0);
    return;
  }

  float z = sqrt(1.0 - rr * rr);
  float s0 = sin(uView.y * DEG);
  float c0 = cos(uView.y * DEG);
  float lat = asin(clamp(z * s0 + q.y * c0, -1.0, 1.0)) / DEG;
  float lon = uView.x + uSpin + atan(q.x, z * c0 - q.y * s0) / DEG;
  vec2 geo = vec2(lon, lat);

  float row = floor(lat / uStep + 0.5);
  float best = 1e9;
  vec2 pick = geo;
  for (int i = -1; i <= 1; i++) {
    float rl = (row + float(i)) * uStep;
    float n = max(1.0, floor(360.0 * cos(rl * DEG) / uStep));
    float dl = 360.0 / n;
    vec2 c = vec2(floor(lon / dl + 0.5) * dl, rl);
    float d = near(geo, c);
    if (d < best) {
      best = d;
      pick = c;
    }
  }
  float isLand = land(pick);

  float lit = 0.0;
  float halo = 0.0;
  for (int i = 0; i < 8; i++) {
    if (i >= uSiteCount) break;
    vec4 s = uSites[i];
    float fi = float(i);
    float on = s.z * (1.0 - smoothstep(front - 2.0, front, arc(s.xy, uOrigin)));
    if (on <= 0.0) continue;
    float breathe = 0.85 + 0.15 * sin(uTime * 0.9 + fi * 2.1);
    float d = near(pick, s.xy) / uStep;
    float core = exp(-d * d / (2.0 + 2.6 * on)) * on * breathe;
    float age = mod(uTime + fi * 1.7, 6.0);
    float ring = exp(-sq(d - age * 3.0) * 1.4) * (1.0 - age / 6.0) * 0.4 * on * uMotion;
    lit += core + ring;
    float dh = near(geo, s.xy) / uStep / 2.6;
    halo += exp(-dh * dh / (2.0 + 2.6 * on)) * on * breathe;
  }
  lit = clamp(lit * mix(0.35, 1.0, isLand), 0.0, 1.0);
  halo = clamp(halo, 0.0, 1.0) * 0.3;

  float fromO = arc(pick, uOrigin);
  float band = exp(-sq((fromO - front) / 1.3))
             * (1.0 - smoothstep(0.75, 1.0, uWave)) * step(0.001, uWave)
             * mix(0.25, 0.85, isLand);
  float ahead = smoothstep(front - 1.5, front + 1.5, fromO) * (1.0 - step(0.999, uWave));

  float shimmer = 0.8 + 0.2 * uMotion * smoothstep(0.2, 0.8, noise(pick * 0.35 + vec2(uTime * 0.05, -uTime * 0.03)));
  float facing = smoothstep(0.0, 0.5, z);
  float offA = (isLand * 0.36 * shimmer + (1.0 - isLand) * 0.05) * facing * mix(1.0, 0.3, ahead);

  float aa = 0.9 / (R * DEG) / max(z, 0.15);
  float radius = uStep * mix(0.24, 0.32, lit);
  float disc = 1.0 - smoothstep(radius - aa, radius + aa, best);

  vec3 onCol = mix(uViolet, vec3(1.0), 0.25 * lit);
  vec3 col = mix(vec3(1.0), onCol, smoothstep(0.0, 0.6, lit));
  float a = disc * mix(offA, 1.0, lit);
  vec3 waveCol = mix(uViolet, vec3(1.0), 0.45);
  col = mix(col, waveCol, band);
  a = max(a, disc * band);

  vec4 surf = over(col, a, uViolet, halo);
  vec4 o = over(surf.rgb, surf.a, atmoCol, atmo);
  float fa = clamp(o.a * edgeFade(), 0.0, 1.0);
  gl_FragColor = vec4(clamp(o.rgb, 0.0, 1.0) * fa, fa);
}`;

function bezier(x1, y1, x2, y2) {
  const cx = 3 * x1, bx = 3 * (x2 - x1) - cx, ax = 1 - cx - bx;
  const cy = 3 * y1, by = 3 * (y2 - y1) - cy, ay = 1 - cy - by;
  const x = (t) => ((ax * t + bx) * t + cx) * t;
  const dx = (t) => (3 * ax * t + 2 * bx) * t + cx;
  const y = (t) => ((ay * t + by) * t + cy) * t;
  return (p) => {
    if (p <= 0) return 0;
    if (p >= 1) return 1;
    let t = p;
    for (let i = 0; i < 6; i++) {
      const d = dx(t);
      if (Math.abs(d) < 1e-6) break;
      t -= (x(t) - p) / d;
    }
    return y(Math.min(1, Math.max(0, t)));
  };
}

const easeExpoOut = bezier(0.16, 1, 0.3, 1);
const easeOut = (t) => 1 - (1 - t) ** 3;
const clamp01 = (t) => Math.min(1, Math.max(0, t));

function arcDeg([lon1, lat1], [lon2, lat2]) {
  const c = Math.sin(lat1 * DEG) * Math.sin(lat2 * DEG)
    + Math.cos(lat1 * DEG) * Math.cos(lat2 * DEG) * Math.cos((lon1 - lon2) * DEG);
  return Math.acos(Math.min(1, Math.max(-1, c))) / DEG;
}

function cssColor(name, fallback) {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const m = /^#([0-9a-f]{6})$/i.exec(v);
  if (!m) return fallback;
  const n = parseInt(m[1], 16);
  return [(n >> 16) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
}

export class Globe {
  /**
   * @param {HTMLElement} host  holds a <canvas> and a .globe-pins layer
   * @param {object} opts
   *   land:    URL of the equirectangular land mask
   *   origin:  [lon, lat] the wave starts from (the visitor)
   *   sites:   [{ id, lon, lat, el }] -- `el` is the marker to place
   *   watch:   element whose visibility decides whether to draw
   */
  constructor(host, opts) {
    this.host = host;
    this.opts = { focus: [15, 53], anchor: 0.66, front: 60, waveDelay: 0.9, waveDur: 1.6, ...opts };
    this.sites = opts.sites || [];
    this.origin = opts.origin || [37.62, 55.75];
    this.canvas = host.querySelector("canvas");
    this.reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
    this.ready = false;
    this.visible = true;
    this.lastDraw = 0;
    this.colors = {
      violet: cssColor("--violet", [0.486, 0.227, 0.929]),
      coral: cssColor("--coral", [1, 0.478, 0.349]),
    };
    this.gl = this.initGL();
    if (!this.gl) host.classList.add("globe--flat");
    this.layout();
    new ResizeObserver(() => this.layout()).observe(host);
    new IntersectionObserver(([e]) => {
      this.visible = e.isIntersecting;
      this.kick();
    }).observe(opts.watch || host);
    document.addEventListener("visibilitychange", () => this.kick());
    if (!this.gl) {
      this.ready = true;
      this.reveal(false);
    }
  }

  initGL() {
    const gl = this.canvas.getContext("webgl", { alpha: true, premultipliedAlpha: true, antialias: false });
    if (!gl) return null;
    const compile = (type, src) => {
      const s = gl.createShader(type);
      gl.shaderSource(s, src);
      gl.compileShader(s);
      if (!gl.getShaderParameter(s, gl.COMPILE_STATUS)) throw new Error(gl.getShaderInfoLog(s));
      return s;
    };
    try {
      const prog = gl.createProgram();
      gl.attachShader(prog, compile(gl.VERTEX_SHADER, VERT));
      gl.attachShader(prog, compile(gl.FRAGMENT_SHADER, FRAG));
      gl.linkProgram(prog);
      if (!gl.getProgramParameter(prog, gl.LINK_STATUS)) throw new Error(gl.getProgramInfoLog(prog));
      gl.useProgram(prog);
      const buf = gl.createBuffer();
      gl.bindBuffer(gl.ARRAY_BUFFER, buf);
      gl.bufferData(gl.ARRAY_BUFFER, new Float32Array([-1, -1, 3, -1, -1, 3]), gl.STATIC_DRAW);
      const loc = gl.getAttribLocation(prog, "aPos");
      gl.enableVertexAttribArray(loc);
      gl.vertexAttribPointer(loc, 2, gl.FLOAT, false, 0, 0);
      this.u = {};
      const count = gl.getProgramParameter(prog, gl.ACTIVE_UNIFORMS);
      for (let i = 0; i < count; i++) {
        const name = gl.getActiveUniform(prog, i).name.replace(/\[0\]$/, "");
        this.u[name] = gl.getUniformLocation(prog, name);
      }
    } catch (err) {
      console.warn("globe: falling back to markers only", err);
      return null;
    }
    const tex = gl.createTexture();
    const img = new Image();
    img.onload = () => {
      gl.bindTexture(gl.TEXTURE_2D, tex);
      gl.texImage2D(gl.TEXTURE_2D, 0, gl.LUMINANCE, gl.LUMINANCE, gl.UNSIGNED_BYTE, img);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MIN_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_MAG_FILTER, gl.LINEAR);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_S, gl.CLAMP_TO_EDGE);
      gl.texParameteri(gl.TEXTURE_2D, gl.TEXTURE_WRAP_T, gl.CLAMP_TO_EDGE);
      gl.uniform1i(this.u.uLand, 0);
      this.ready = true;
      this.start = performance.now();
      this.host.classList.add("is-ready");
      this.reveal(!this.reduced);
      this.kick();
    };
    img.onerror = () => {
      this.ready = true;
      this.reveal(false);
    };
    img.src = this.opts.land;
    return gl;
  }

  layout() {
    const w = this.host.clientWidth;
    const h = this.host.clientHeight;
    if (!w || !h) return;
    const narrow = w < 640;
    const R = (narrow ? 1.6 : 2.6) * h;
    const cx = w * (narrow ? 0.5 : this.opts.anchor);
    const cy = 0.1 * h + R;
    const [flon, flat] = this.opts.focus;
    const lat0 = flat - Math.asin(Math.min(1, (cy - 0.55 * h) / R)) / DEG;
    this.geo = { w, h, R, cx, cy, lon0: flon, lat0, step: 8.5 / (R * DEG), narrow };
    if (this.gl) {
      const dpr = Math.min(1.5, devicePixelRatio || 1, Math.sqrt(1.6e6 / (w * h)));
      this.dpr = dpr;
      this.canvas.width = Math.round(w * dpr);
      this.canvas.height = Math.round(h * dpr);
      this.canvas.style.width = `${w}px`;
      this.canvas.style.height = `${h}px`;
      this.gl.viewport(0, 0, this.canvas.width, this.canvas.height);
    }
    this.placeSites();
    this.kick();
  }

  project([lon, lat]) {
    const g = this.geo;
    const dl = (lon - g.lon0) * DEG;
    const p = lat * DEG;
    const p0 = g.lat0 * DEG;
    const x = Math.cos(p) * Math.sin(dl);
    const y = Math.cos(p0) * Math.sin(p) - Math.sin(p0) * Math.cos(p) * Math.cos(dl);
    const cosc = Math.sin(p0) * Math.sin(p) + Math.cos(p0) * Math.cos(p) * Math.cos(dl);
    return { x: g.cx + x * g.R, y: g.cy - y * g.R, visible: cosc > 0 };
  }

  placeSites() {
    if (!this.geo) return;
    for (const s of this.sites) {
      if (!s.el) continue;
      const p = this.project([s.lon, s.lat]);
      s.el.style.left = `${p.x}px`;
      s.el.style.top = `${p.y}px`;
      s.el.hidden = !p.visible;
    }
  }

  /** Move the wave's origin, e.g. once the visitor's city is known. */
  setOrigin(origin) {
    this.origin = origin;
    this.kick();
  }

  /** Markers rise in as the wave reaches them, or appear at once. */
  reveal(animate) {
    const o = this.opts;
    for (const s of this.sites) {
      if (!s.el) continue;
      s.el.classList.remove("is-in", "is-settled");
      if (!animate) {
        s.el.classList.add("is-settled");
        continue;
      }
      const at = o.waveDelay + o.waveDur * clamp01(arcDeg([s.lon, s.lat], this.origin) / o.front);
      s.el.style.setProperty("--pin-delay", `${at.toFixed(3)}s`);
      void s.el.offsetWidth;
      s.el.classList.add("is-in");
    }
    this.introOn = animate;
  }

  kick() {
    if (this.raf || !this.gl || !this.ready) return;
    this.raf = requestAnimationFrame((t) => this.frame(t));
  }

  frame(now) {
    this.raf = 0;
    if (!this.visible || document.hidden) return;
    const o = this.opts;
    const t = (now - this.start) / 1000;
    const intro = this.introOn && t < o.waveDelay + o.waveDur + 0.2;
    // Full rate only while the intro moves; the rest is a slow twinkle.
    if (intro || now - this.lastDraw >= 32) {
      this.lastDraw = now;
      this.draw(t);
    }
    if (!this.reduced || t < 0.2) this.kick();
  }

  draw(t) {
    const gl = this.gl;
    const u = this.u;
    const g = this.geo;
    const o = this.opts;
    let rise = 0;
    let spin = 0;
    let atmo = 1;
    let wave = 1;
    if (this.introOn) {
      const k = easeExpoOut(clamp01(t / 1.5));
      rise = 0.5 * g.h * (1 - k);
      spin = 24 * (1 - k);
      atmo = easeOut(clamp01(t / 1.2));
      wave = clamp01((t - o.waveDelay) / o.waveDur);
    }
    gl.uniform2f(u.uRes, this.canvas.width, this.canvas.height);
    gl.uniform1f(u.uDpr, this.dpr);
    gl.uniform1f(u.uTime, this.reduced ? 4 : t);
    gl.uniform1f(u.uMotion, this.reduced ? 0 : 1);
    gl.uniform3f(u.uGlobe, g.cx, g.cy, g.R);
    gl.uniform2f(u.uView, g.lon0, g.lat0);
    gl.uniform1f(u.uStep, g.step);
    gl.uniform1f(u.uRise, rise);
    gl.uniform1f(u.uSpin, spin);
    gl.uniform1f(u.uAtmo, atmo);
    gl.uniform1f(u.uWave, wave);
    gl.uniform1f(u.uFront, o.front);
    gl.uniform2f(u.uOrigin, this.origin[0], this.origin[1]);
    gl.uniform3fv(u.uViolet, this.colors.violet);
    gl.uniform3fv(u.uCoral, this.colors.coral);
    gl.uniform4f(u.uFade, ...(g.narrow ? [0.04, 0.04, 0.02, 0.14] : [0.34, 0.04, 0.02, 0.08]));
    const arr = new Float32Array(32);
    this.sites.slice(0, 8).forEach((s, i) => arr.set([s.lon, s.lat, 1, 1], i * 4));
    gl.uniform4fv(u.uSites, arr);
    gl.uniform1i(u.uSiteCount, Math.min(8, this.sites.length));
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }
}
