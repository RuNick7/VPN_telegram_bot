/*
 * The landing page's planet: a night Earth in the brand's colours, with a
 * comet flying from the visitor to each server and the round trip shown when
 * it lands.
 *
 * Two canvases, one projection. The sphere is a single WebGL fragment shader
 * (every pixel is projected back onto the globe and coloured from a land mask:
 * soft land, glowing coastlines, a few warm city lights). The comets, bursts
 * and their trails go on a 2D canvas above it, and the markers and the ping
 * card are ordinary DOM above that, placed through the CSSOM so the page keeps
 * a CSP without 'unsafe-inline'.
 *
 * The cabinet's dotted globe is a different piece (assets/js/globe.js); the two
 * share only the land mask's projection, not their look.
 */

const DEG = Math.PI / 180;

const VERT = `
attribute vec2 aPos;
void main() {
  gl_Position = vec4(aPos, 0.0, 1.0);
}`;

const FRAG = `
precision highp float;
uniform vec2 uRes;
uniform float uDpr;
uniform float uTime;
uniform sampler2D uLand;
uniform vec3 uGlobe;
uniform vec2 uView;
uniform float uRise;
uniform float uAtmo;
uniform vec3 uViolet;
uniform vec3 uLilac;
uniform vec3 uCoral;
uniform vec3 uPink;
uniform vec4 uHot[6];
uniform int uHotCount;

const float DEG = 0.017453292;

float sq(float x) { return x * x; }

float hash(vec2 p) {
  p = fract(p * vec2(123.34, 456.21));
  p += dot(p, p + 45.32);
  return fract(p.x * p.y);
}

float mask(vec2 g) {
  return texture2D(uLand, vec2(fract((g.x + 180.0) / 360.0), clamp((90.0 - g.y) / 180.0, 0.0, 1.0))).r;
}

float near(vec2 a, vec2 b) {
  float dl = mod(a.x - b.x + 540.0, 360.0) - 180.0;
  return length(vec2(dl * cos(b.y * DEG), a.y - b.y));
}

void main() {
  vec2 css = vec2(gl_FragCoord.x, uRes.y - gl_FragCoord.y) / uDpr;
  float R = uGlobe.z;
  vec2 q = (css - vec2(uGlobe.x, uGlobe.y + uRise)) / R;
  q.y = -q.y;
  float rr = length(q);
  float edge = (rr - 1.0) * R;

  // The horizon is lilac on the left and warms through coral to pink on the
  // right: the same order as the colours run in the logo.
  float hx = clamp(css.x / (uRes.x / uDpr), 0.0, 1.0);
  vec3 warm = mix(uCoral, uPink, smoothstep(0.7, 1.0, hx));
  vec3 rimCol = mix(mix(uLilac, uViolet, 0.25), warm, smoothstep(0.5, 0.95, hx));

  // Three falloffs: the bright rim, the atmosphere, and a wide haze that
  // carries the colour up towards the top of the hero so space and planet
  // read as one picture.
  float e = max(edge, 0.0);
  float halo = (exp(-e / 16.0) * 0.6 + exp(-e / 80.0) * 0.25 + exp(-e / 300.0) * 0.2) * uAtmo;
  float inside = clamp(-edge / 1.2, 0.0, 1.0);

  vec3 col = vec3(0.0);
  if (rr < 1.0) {
    float z = sqrt(1.0 - rr * rr);
    float s0 = sin(uView.y * DEG);
    float c0 = cos(uView.y * DEG);
    float lat = asin(clamp(z * s0 + q.y * c0, -1.0, 1.0)) / DEG;
    float lon = uView.x + atan(q.x, z * c0 - q.y * s0) / DEG;
    vec2 geo = vec2(lon, lat);

    vec3 n = vec3(q, z);
    float diff = clamp(dot(n, normalize(vec3(-0.2, 0.85, 0.5))), 0.0, 1.0);
    float rim = pow(1.0 - z, 2.4);
    float dpix = 1.0 / (R * DEG) / max(z, 0.2);

    float m = mask(geo);
    float land = smoothstep(0.3, 0.7, m);
    float coast = pow(1.0 - smoothstep(0.0, 0.5, abs(m - 0.5)), 2.0);

    // Glow pools where the visitor and the servers are.
    float hot = 0.0;
    vec3 hotCol = vec3(0.0);
    for (int i = 0; i < 6; i++) {
      if (i >= uHotCount) break;
      vec4 h = uHot[i];
      float k = exp(-sq(near(geo, h.xy) / 2.2)) * h.z;
      hot += k;
      hotCol += (h.w > 0.5 ? uCoral : uLilac) * k;
    }
    hotCol /= max(hot, 0.0001);
    hot = clamp(hot, 0.0, 1.0);

    // City lights: a sparse scatter over land, denser around the glow pools.
    vec2 cell = floor(geo / 0.55);
    float hc = hash(cell);
    vec2 cpos = (cell + vec2(hash(cell + 3.1), hash(cell + 7.7))) * 0.55;
    float lit = step(0.88 - 0.35 * hot, hc) * land;
    float tw = 0.7 + 0.3 * sin(uTime * 1.4 + hc * 40.0);
    float spark = lit * exp(-sq(near(geo, cpos) / (dpix * 1.3))) * tw;

    vec3 ocean = mix(vec3(0.025, 0.016, 0.06), vec3(0.075, 0.04, 0.16), diff);
    vec3 ground = mix(vec3(0.085, 0.055, 0.17), vec3(0.2, 0.13, 0.36), diff);
    col = mix(ocean, ground, land);
    col = mix(col, uLilac, coast * (0.35 + 0.35 * diff));
    col += hotCol * hot * 0.22;
    col += mix(uCoral, vec3(1.0, 0.86, 0.72), 0.45) * spark * 0.85;
    col = mix(col, rimCol, rim * 0.8 * uAtmo);
    col += rimCol * exp(edge / 9.0) * 0.5 * uAtmo;
  }

  vec3 outC = col * inside + rimCol * halo * (1.0 - inside);
  float outA = inside + clamp(halo, 0.0, 1.0) * (1.0 - inside);
  gl_FragColor = vec4(clamp(outC, 0.0, 1.0), outA);
}`;

function cssColor(name, fallback) {
  const v = getComputedStyle(document.documentElement).getPropertyValue(name).trim();
  const m = /^#([0-9a-f]{6})$/i.exec(v);
  if (!m) return fallback;
  const n = parseInt(m[1], 16);
  return [(n >> 16) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
}

const rgb = (c, a) => `rgba(${Math.round(c[0] * 255)}, ${Math.round(c[1] * 255)}, ${Math.round(c[2] * 255)}, ${a})`;
const mixc = (a, b, k) => [a[0] + (b[0] - a[0]) * k, a[1] + (b[1] - a[1]) * k, a[2] + (b[2] - a[2]) * k];
const clamp01 = (t) => Math.min(1, Math.max(0, t));
const easeInOut = (t) => (t < 0.5 ? 4 * t * t * t : 1 - (-2 * t + 2) ** 3 / 2);
const easeOutExpo = (t) => (t >= 1 ? 1 : 1 - 2 ** (-10 * t));

function vec([lon, lat]) {
  return [Math.cos(lat * DEG) * Math.cos(lon * DEG), Math.cos(lat * DEG) * Math.sin(lon * DEG), Math.sin(lat * DEG)];
}

/** Great-circle distance in kilometres. */
export function distanceKm(a, b) {
  const [x1, y1, z1] = vec(a);
  const [x2, y2, z2] = vec(b);
  return Math.acos(Math.max(-1, Math.min(1, x1 * x2 + y1 * y2 + z1 * z2))) * 6371;
}

const FLIGHT = 1.4; // seconds from launch to landing
const HOLD = 2.6;   // seconds the result stays before the next comet

export class Planet {
  /**
   * @param {HTMLElement} root  holds canvas.planet-gl, canvas.planet-fx, .planet-pins
   * @param {object} opts
   *   land:    URL of the equirectangular land mask
   *   origin:  { lon, lat, label }  the visitor
   *   cities:  [{ id, lon, lat, ... }]
   *   onLand:  (city) => void       called as each comet lands
   */
  constructor(root, opts) {
    this.root = root;
    this.opts = opts;
    this.cities = opts.cities;
    this.origin = opts.origin;
    this.gl3 = root.querySelector(".planet-gl");
    this.fx = root.querySelector(".planet-fx");
    this.ctx = this.fx.getContext("2d");
    this.pins = root.querySelector(".planet-pins");
    this.reduced = matchMedia("(prefers-reduced-motion: reduce)").matches;
    this.start = performance.now();
    this.visible = true;
    this.ready = false;
    this.heat = new Map(this.cities.map((c) => [c.id, 0]));
    this.flight = null;
    this.queue = 0;
    this.lastDraw = 0;
    this.fxBox = null;
    // Read once: getComputedStyle inside the frame loop forces a style
    // recalculation whenever anything on the page has changed since.
    this.colors = {
      violet: cssColor("--violet", [0.486, 0.227, 0.929]),
      lilac: cssColor("--lilac", [0.643, 0.502, 0.988]),
      coral: cssColor("--coral", [1, 0.478, 0.349]),
      pink: cssColor("--pink", [0.941, 0.314, 0.431]),
    };

    this.gl = this.initGL();
    if (!this.gl) root.classList.add("planet--flat");
    this.buildPins();
    this.layout();
    // The copy changes height when the config arrives (the free-period line)
    // and when fonts load, and the horizon follows it.
    const resized = new ResizeObserver(() => this.layout());
    resized.observe(root);
    if (opts.clearOf) resized.observe(opts.clearOf);
    // Watch the hero, not the canvas: the canvas runs on under the light page,
    // so it "intersects" the screen long after the planet is out of sight,
    // and drawing it there is GPU time taken from scrolling.
    new IntersectionObserver(([e]) => {
      this.visible = e.isIntersecting;
      this.kick();
    }).observe(opts.hero || root);
    document.addEventListener("visibilitychange", () => this.kick());
    if (!this.gl) this.ready = true;
  }

  initGL() {
    const gl = this.gl3.getContext("webgl", { alpha: true, premultipliedAlpha: true, antialias: false });
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
      console.warn("planet: falling back to the flat version", err);
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
      this.root.classList.add("is-ready");
      this.kick();
    };
    img.onerror = () => {
      this.ready = true;
      this.kick();
    };
    img.src = this.opts.land;
    return gl;
  }

  layout() {
    // The canvas is one tall picture: the hero plus a stretch below it. The
    // horizon goes just under whatever the copy above it measures on this
    // screen, so a phone, a tall monitor and an ultrawide all get the planet
    // starting right where the text ends.
    const w = this.root.clientWidth;
    const h = this.root.clientHeight;
    const narrow = w < 700;
    const box = this.root.getBoundingClientRect();
    const heroH = this.opts.hero ? this.opts.hero.clientHeight : h;
    const copyBottom = this.opts.clearOf ? this.opts.clearOf.getBoundingClientRect().bottom - box.top : heroH * 0.6;
    const top = Math.round(copyBottom + (narrow ? 26 : 40));
    const R = narrow ? w * 1.45 : Math.max(w * 0.86, 920);
    const cx = w / 2;
    const cy = top + R;
    // The servers' latitude band sits midway between the horizon and the
    // location bar along the bottom of the hero.
    const focus = [16, 54.5];
    const bar = this.opts.barSpace ?? 130;
    const fy = top + Math.max(40, heroH - top - bar) * 0.5;
    const lat0 = focus[1] - Math.asin(Math.min(1, (cy - fy) / R)) / DEG;
    this.geo = { w, h, heroH, R, cx, cy, lon0: focus[0], lat0 };

    // A tall canvas is a lot of pixels: hold the shader to about 2.5 million
    // and the 2D layer to about 3 million, whatever the screen's density.
    // The picture is soft glow and small dots; more than that buys nothing
    // visible and costs the GPU time scrolling needs.
    const area = Math.max(1, w * h);
    const dprGL = Math.min(1.5, devicePixelRatio || 1, Math.sqrt(2.5e6 / area));
    const dprFx = Math.min(2, devicePixelRatio || 1, Math.sqrt(3e6 / area));
    this.dprGL = dprGL;
    this.dprFx = dprFx;
    this.fxBox = null; // resizing a canvas clears it
    for (const [c, d] of [[this.gl3, dprGL], [this.fx, dprFx]]) {
      c.width = Math.round(w * d);
      c.height = Math.round(h * d);
      c.style.width = `${w}px`;
      c.style.height = `${h}px`;
    }
    if (this.gl) this.gl.viewport(0, 0, this.gl3.width, this.gl3.height);
    this.placePins();
    this.kick();
  }

  /** Screen position of a point `lift` sphere-radii above the surface. */
  project([lon, lat], lift = 0, rise = this.rise || 0) {
    const g = this.geo;
    const dl = (lon - g.lon0) * DEG;
    const p = lat * DEG;
    const p0 = g.lat0 * DEG;
    const s = 1 + lift;
    const x = Math.cos(p) * Math.sin(dl) * s;
    const y = (Math.cos(p0) * Math.sin(p) - Math.sin(p0) * Math.cos(p) * Math.cos(dl)) * s;
    const z = (Math.sin(p0) * Math.sin(p) + Math.cos(p0) * Math.cos(p) * Math.cos(dl)) * s;
    const visible = z > 0 || x * x + y * y > 1;
    return { x: g.cx + x * g.R, y: g.cy + rise - y * g.R, visible };
  }

  buildPins() {
    this.pins.replaceChildren();
    const you = document.createElement("div");
    you.className = "pin pin--you";
    you.innerHTML = '<span class="pin-ping"></span><span class="pin-dot"></span><span class="pin-label"></span>';
    you.querySelector(".pin-label").textContent = this.origin.label;
    this.youPin = you;
    this.pins.append(you);
    for (const c of this.cities) {
      const pin = document.createElement("div");
      pin.className = "pin pin--server";
      pin.innerHTML = '<span class="pin-dot"></span>';
      c.pin = pin;
      this.pins.append(pin);
    }
  }

  placePins() {
    if (!this.geo) return;
    const put = (el, lonlat) => {
      const p = this.project(lonlat);
      el.style.left = `${p.x}px`;
      el.style.top = `${p.y}px`;
      el.hidden = !p.visible;
      return p;
    };
    put(this.youPin, [this.origin.lon, this.origin.lat]);
    for (const c of this.cities) put(c.pin, [c.lon, c.lat]);
    if (this.card && this.cardCity) {
      const p = put(this.card, [this.cardCity.lon, this.cardCity.lat]);
      // Right of the city if it fits, else left, else underneath.
      const need = this.card.offsetWidth + 32;
      const right = p.x + need <= this.geo.w;
      const left = p.x - need >= 0;
      this.card.classList.toggle("is-left", !right && left);
      this.card.classList.toggle("is-below", !right && !left);
    }
  }

  setOrigin(origin) {
    this.origin = origin;
    this.youPin.querySelector(".pin-label").textContent = origin.label;
    this.placePins();
  }

  /** Attach the ping card element that follows whichever city was hit last. */
  setCard(card) {
    this.card = card;
    this.pins.append(card);
  }

  /** Send a comet to one city now; the automatic round resumes after it. */
  fly(index) {
    const city = this.cities[index];
    this.queue = index;
    for (const c of this.cities) c.pin.classList.toggle("is-target", c === city);
    if (this.reduced) {
      // No flight under reduced motion: the result appears straight away.
      this.cardCity = city;
      this.heat.set(city.id, 1);
      this.opts.onLand?.(city);
      this.placePins();
      this.kick();
      return;
    }
    this.flight = { city, t0: (performance.now() - this.start) / 1000, landed: false };
    this.kick();
  }

  /**
   * Show one city's result straight away, as if its comet had just landed:
   * what a click on a location asks for. The beam still flashes along the
   * route and fades, and the automatic round carries on from there.
   */
  jump(index) {
    if (this.reduced) {
      this.fly(index);
      return;
    }
    const city = this.cities[index];
    this.queue = index;
    for (const c of this.cities) c.pin.classList.toggle("is-target", c === city);
    this.flight = { city, t0: (performance.now() - this.start) / 1000 - FLIGHT, landed: false };
    this.kick();
  }

  path(city) {
    const a = vec([this.origin.lon, this.origin.lat]);
    const b = vec([city.lon, city.lat]);
    const dot = Math.max(-1, Math.min(1, a[0] * b[0] + a[1] * b[1] + a[2] * b[2]));
    const omega = Math.acos(dot);
    const lift = 0.02 + 0.09 * Math.min(1, omega / (60 * DEG));
    return (t) => {
      let v;
      if (omega < 1e-4) v = a;
      else {
        const s = Math.sin(omega);
        const ka = Math.sin((1 - t) * omega) / s;
        const kb = Math.sin(t * omega) / s;
        v = [a[0] * ka + b[0] * kb, a[1] * ka + b[1] * kb, a[2] * ka + b[2] * kb];
      }
      const lat = Math.asin(Math.max(-1, Math.min(1, v[2]))) / DEG;
      const lon = Math.atan2(v[1], v[0]) / DEG;
      return this.project([lon, lat], lift * Math.sin(Math.PI * t));
    };
  }

  kick() {
    if (this.raf || !this.ready) return;
    this.raf = requestAnimationFrame((now) => this.frame(now));
  }

  frame(now) {
    this.raf = 0;
    if (!this.visible || document.hidden) return;
    const t = (now - this.start) / 1000;
    const g = this.geo;

    const dt = Math.min(0.1, Math.max(0, t - (this.lastT ?? t)));
    this.lastT = t;

    // Intro: the planet rises into place and its atmosphere comes up.
    const k = this.reduced ? 1 : easeOutExpo(clamp01(t / 1.6));
    this.rise = 0.35 * g.heroH * (1 - k);
    const atmo = this.reduced ? 1 : clamp01(t / 1.1);
    if (k < 1) this.placePins();
    const risen = k > 0.92;
    if (risen !== this.risen) {
      this.risen = risen;
      this.root.classList.toggle("is-risen", risen);
    }

    // The round: launch, land, hold, next.
    if (!this.flight && t > 1.3 && !this.reduced) this.fly(this.queue);
    if (this.flight) {
      const ft = t - this.flight.t0;
      if (!this.flight.landed && ft >= FLIGHT) {
        this.flight.landed = true;
        this.heat.set(this.flight.city.id, 1);
        this.cardCity = this.flight.city;
        // Fill the card first, so placing it measures the new text.
        this.opts.onLand?.(this.flight.city);
        this.placePins();
      }
      if (ft >= FLIGHT + HOLD) this.fly((this.cities.indexOf(this.flight.city) + 1) % this.cities.length);
    }
    for (const [id, v] of this.heat) this.heat.set(id, Math.max(0.35, v - 0.24 * dt));

    // Frame rates. The sphere itself changes slowly (a twinkle, a fading glow)
    // and is the expensive part, so it draws at half rate except while the
    // intro moves it. The comet and its rings move fast but sit on the cheap
    // 2D layer, which runs at full rate while there is one in the air. The
    // GPU time saved is time scrolling gets.
    const f = this.flight;
    const fastFx = !this.reduced && Boolean(f) && t - f.t0 < FLIGHT + 1.6;
    const fastGL = !this.reduced && k < 1;
    if (fastGL || now - this.lastDraw >= 32) {
      this.lastDraw = now;
      this.drawGL(t, atmo);
    }
    if (fastFx || this.fxBox || now - (this.lastFx || 0) >= 32) {
      this.lastFx = now;
      this.drawFx(t);
    }
    if (!this.reduced || t < 2) this.kick();
  }

  drawGL(t, atmo) {
    const gl = this.gl;
    if (!gl) return;
    const u = this.u;
    const g = this.geo;
    gl.uniform2f(u.uRes, this.gl3.width, this.gl3.height);
    gl.uniform1f(u.uDpr, this.dprGL);
    gl.uniform1f(u.uTime, this.reduced ? 3 : t);
    gl.uniform3f(u.uGlobe, g.cx, g.cy, g.R);
    gl.uniform2f(u.uView, g.lon0, g.lat0);
    gl.uniform1f(u.uRise, this.rise);
    gl.uniform1f(u.uAtmo, atmo);
    gl.uniform3fv(u.uViolet, this.colors.violet);
    gl.uniform3fv(u.uLilac, this.colors.lilac);
    gl.uniform3fv(u.uCoral, this.colors.coral);
    gl.uniform3fv(u.uPink, this.colors.pink);
    const hot = new Float32Array(24);
    hot.set([this.origin.lon, this.origin.lat, 0.9, 1], 0);
    this.cities.slice(0, 5).forEach((c, i) => hot.set([c.lon, c.lat, this.heat.get(c.id), 0], (i + 1) * 4));
    gl.uniform4fv(u.uHot, hot);
    gl.uniform1i(u.uHotCount, 1 + Math.min(5, this.cities.length));
    gl.drawArrays(gl.TRIANGLES, 0, 3);
  }

  /** The screen rectangle a route and its landing rings can reach. */
  routeBox(path) {
    let x0 = Infinity;
    let y0 = Infinity;
    let x1 = -Infinity;
    let y1 = -Infinity;
    for (let i = 0; i <= 24; i++) {
      const p = path(i / 24);
      x0 = Math.min(x0, p.x);
      y0 = Math.min(y0, p.y);
      x1 = Math.max(x1, p.x);
      y1 = Math.max(y1, p.y);
    }
    const pad = 64; // the rings spread 47px, the comet's glow 16px
    return [x0 - pad, y0 - pad, x1 - x0 + 2 * pad, y1 - y0 + 2 * pad];
  }

  drawFx(t) {
    const ctx = this.ctx;
    const d = this.dprFx;
    ctx.setTransform(d, 0, 0, d, 0, 0);
    const { lilac, coral } = this.colors;
    ctx.lineCap = "round";

    if (this.reduced) {
      // A still picture: every route drawn once, faintly.
      ctx.clearRect(0, 0, this.geo.w, this.geo.h);
      for (const c of this.cities) this.trace(this.path(c), 1, 0.35, lilac, coral);
      return;
    }

    // Clear only what was drawn last frame and what is about to be: the
    // canvas is the whole tall picture, a route is a small part of it, and
    // most of the time nothing is drawn at all.
    const f = this.flight;
    const live = Boolean(f) && t - f.t0 < FLIGHT + 1.6;
    const path = live ? this.path(f.city) : null;
    const box = live ? this.routeBox(path) : null;
    if (this.fxBox) ctx.clearRect(...this.fxBox);
    if (box) ctx.clearRect(...box);
    this.fxBox = box;
    if (!live) return;
    const ft = t - f.t0;
    const p = clamp01(ft / FLIGHT);
    const e = easeInOut(p);

    // The beam: a faint line behind the comet that fades once it has landed.
    const fade = f.landed ? clamp01(1 - (ft - FLIGHT) / 0.9) : 1;
    if (fade > 0) this.trace(path, e, 0.22 * fade, lilac, coral);

    if (!f.landed) {
      // The comet: a tail that brightens and thickens towards the head.
      const tail = 0.3;
      const t0 = Math.max(0, e - tail);
      const N = 40;
      let prev = path(t0);
      for (let i = 1; i <= N; i++) {
        const k = i / N;
        const pt = path(t0 + (e - t0) * k);
        if (prev.visible && pt.visible) {
          ctx.strokeStyle = rgb(mixc(lilac, coral, k), k * k * 0.95);
          ctx.lineWidth = 0.6 + 2.4 * k;
          ctx.beginPath();
          ctx.moveTo(prev.x, prev.y);
          ctx.lineTo(pt.x, pt.y);
          ctx.stroke();
        }
        prev = pt;
      }
      const head = path(e);
      if (head.visible) {
        const glow = ctx.createRadialGradient(head.x, head.y, 0, head.x, head.y, 16);
        glow.addColorStop(0, "rgba(255, 255, 255, 0.95)");
        glow.addColorStop(0.25, rgb(coral, 0.7));
        glow.addColorStop(1, rgb(coral, 0));
        ctx.fillStyle = glow;
        ctx.beginPath();
        ctx.arc(head.x, head.y, 16, 0, Math.PI * 2);
        ctx.fill();
      }
    } else {
      // The landing: two rings spreading from the city.
      const end = path(1);
      for (const delay of [0, 0.28]) {
        const age = ft - FLIGHT - delay;
        if (age < 0 || age > 1.3) continue;
        const k = age / 1.3;
        ctx.strokeStyle = rgb(mixc(coral, lilac, k), (1 - k) * 0.9);
        ctx.lineWidth = 1.6;
        ctx.beginPath();
        ctx.arc(end.x, end.y, 5 + 42 * (1 - (1 - k) ** 3), 0, Math.PI * 2);
        ctx.stroke();
      }
    }
  }

  trace(path, upto, alpha, a, b) {
    const ctx = this.ctx;
    const N = 48;
    let prev = path(0);
    for (let i = 1; i <= N; i++) {
      const k = (i / N) * upto;
      const pt = path(k);
      if (prev.visible && pt.visible) {
        ctx.strokeStyle = rgb(mixc(a, b, k), alpha);
        ctx.lineWidth = 1.2;
        ctx.beginPath();
        ctx.moveTo(prev.x, prev.y);
        ctx.lineTo(pt.x, pt.y);
        ctx.stroke();
      }
      prev = pt;
    }
  }
}
