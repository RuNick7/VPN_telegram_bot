/*
 * Shared runtime for every page.
 *
 * Two rules hold everywhere below and are worth stating once:
 *
 *  - Nothing from the server is ever assigned to innerHTML. Text goes through
 *    textContent and structure is built from elements. An email address or a
 *    Telegram tag is attacker-controlled, and this is the only place a stored
 *    XSS could plausibly get in.
 *  - Every fetch is same-origin with credentials. The session lives in a
 *    __Host- HttpOnly cookie that JavaScript cannot read, so there is no token
 *    here to leak in the first place.
 */

export class ApiError extends Error {
  constructor(status, code, message) {
    super(message || "Что-то пошло не так.");
    this.status = status;
    this.code = code || "error";
  }
}

/** Calls the JSON API. Throws ApiError for anything that is not 2xx. */
export async function api(path, { method = "GET", body } = {}) {
  let response;
  try {
    response = await fetch(path, {
      method,
      credentials: "same-origin",
      headers: body === undefined ? {} : { "Content-Type": "application/json" },
      body: body === undefined ? undefined : JSON.stringify(body),
    });
  } catch {
    // Offline, DNS failure, or the connection was cut. The API never produced
    // an answer, so saying "server error" would be a guess.
    throw new ApiError(0, "offline", "Нет связи с сервером. Проверьте подключение.");
  }

  const payload = await response.json().catch(() => null);
  if (!response.ok) {
    throw new ApiError(response.status, payload?.error, payload?.message);
  }
  return payload;
}

/**
 * Sends the visitor to sign in, remembering where they were.
 *
 * The `next` value is a path only, and is validated again on the way back out
 * — a redirect target taken from the URL is how open redirects happen.
 */
export function toLogin() {
  const here = location.pathname + location.search;
  location.replace("/login?next=" + encodeURIComponent(here));
}

/** A same-origin path from an untrusted string, or the fallback. */
export function safePath(value, fallback = "/app") {
  if (typeof value !== "string") return fallback;
  // A leading `//` is a protocol-relative URL to another host, and a backslash
  // is normalised to a slash by several browsers — both bypass a naive check.
  if (!value.startsWith("/") || value.startsWith("//") || value.startsWith("/\\")) {
    return fallback;
  }
  return value;
}

/** Runs a guarded page: on 401 it redirects instead of showing an error. */
export async function guarded(run) {
  try {
    await run();
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      toLogin();
      return;
    }
    console.error(err);
    flash(err instanceof ApiError ? err.message : "Что-то пошло не так.");
  }
}

// -- DOM ------------------------------------------------------------------

export const $ = (selector, root = document) => root.querySelector(selector);
export const $$ = (selector, root = document) => [...root.querySelectorAll(selector)];

/**
 * Creates an element. Text is set as text, never parsed as markup.
 *
 * `false` drops the attribute entirely and `true` writes the string "true".
 * The HTML convention for a boolean attribute is an empty value, and that is
 * what this used to write — but every selector in the stylesheet reads
 * `[data-x="true"]`, which an empty value does not match. Three things were
 * silently inert because of it: the device pips on the overview never lit up,
 * the best-value plan was never highlighted, and a spent gift was never dimmed.
 * "true" is equally valid on real boolean attributes, where any value means
 * true, so `readonly` and `muted` are unaffected.
 */
export function el(tag, props = {}, children = []) {
  const node = document.createElement(tag);
  for (const [key, value] of Object.entries(props)) {
    if (value === undefined || value === null || value === false) continue;
    if (key === "class") node.className = value;
    else if (key === "text") node.textContent = value;
    else if (key === "html") throw new Error("el(): refusing to set raw HTML");
    else if (key.startsWith("on")) node.addEventListener(key.slice(2), value);
    else node.setAttribute(key, String(value));
  }
  for (const child of [].concat(children)) {
    if (child) node.append(child);
  }
  return node;
}

/**
 * An <svg><use> pointing into the sprite.
 *
 * A bare fragment, not a file path: the sprite is inlined into every page by
 * the server, because Chromium and WebKit do not resolve `<use>` against an
 * external document — they render nothing and say nothing about it.
 */
export function icon(name, extraClass = "") {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", ("icon " + extraClass).trim());
  svg.setAttribute("aria-hidden", "true");
  const use = document.createElementNS("http://www.w3.org/2000/svg", "use");
  use.setAttribute("href", `#i-${name}`);
  svg.append(use);
  return svg;
}

export function setText(selector, value, root = document) {
  const node = $(selector, root);
  if (node) {
    node.textContent = value;
    node.classList.remove("skeleton");
  }
  return node;
}

export function show(node, visible = true) {
  if (node) node.hidden = !visible;
}

/**
 * Shows a message in the page's notice slot, or falls back to an alert.
 *
 * The slot is pinned to the viewport (see `.notice[data-notice]`), so this no
 * longer depends on the reader happening to be looking at the top of the page.
 * It carries a dismiss button for the same reason: something fixed over the
 * content has to be closable, or it sits on the footer until the next action.
 */
export function flash(message, kind = "error") {
  const slot = $("[data-notice]");
  if (!slot) {
    alert(message);
    return;
  }

  const close = el("button", {
    class: "notice-close",
    type: "button",
    "aria-label": "Закрыть уведомление",
  });
  close.append(icon("close"));
  close.addEventListener("click", clearFlash);

  slot.textContent = "";
  slot.append(
    icon(kind === "ok" ? "check-circle" : "warning"),
    el("span", { text: message }),
    close
  );
  slot.dataset.kind = kind;
  slot.hidden = false;
}

export function clearFlash() {
  const slot = $("[data-notice]");
  if (slot) slot.hidden = true;
}

/**
 * Runs an async action while a button shows it is working.
 *
 * Also guards against the double submit: a second click while the first is in
 * flight would create a second YooKassa payment.
 */
export async function withBusy(button, action) {
  if (!button || button.dataset.busy === "1") return;
  button.dataset.busy = "1";
  button.setAttribute("aria-busy", "true");
  button.disabled = true;
  try {
    return await action();
  } finally {
    delete button.dataset.busy;
    button.removeAttribute("aria-busy");
    button.disabled = false;
  }
}

// -- formatting -----------------------------------------------------------

const dateFmt = new Intl.DateTimeFormat("ru-RU", {
  day: "2-digit",
  month: "2-digit",
  year: "numeric",
});

export function formatDate(unixSeconds) {
  if (!unixSeconds) return "—";
  return dateFmt.format(new Date(unixSeconds * 1000));
}

export function formatRub(amount) {
  return new Intl.NumberFormat("ru-RU").format(amount) + " ₽";
}

export function formatGB(bytes) {
  if (!bytes || bytes <= 0) return "0";
  const gb = bytes / 1024 ** 3;
  return gb >= 10 ? Math.round(gb).toString() : gb.toFixed(1).replace(/\.0$/, "");
}

/** "5 дней" — Russian needs three forms, and "5 день" reads as broken. */
export function plural(n, one, few, many) {
  const abs = Math.abs(n) % 100;
  const last = abs % 10;
  if (abs > 10 && abs < 20) return many;
  if (last > 1 && last < 5) return few;
  if (last === 1) return one;
  return many;
}

export function daysLabel(n) {
  return `${n} ${plural(n, "день", "дня", "дней")}`;
}

/**
 * Pulls a promo code out of whatever the customer pasted.
 *
 * A gift reaches people two ways -- as a code to type into the bot, and as a
 * `https://…/gift/CODE` link for anyone who does not use Telegram -- and a
 * recipient is as likely to paste the whole link as to pick the code out of
 * it. Both arrive here. The same function reads the code off the gift page's
 * own path, so the two routes cannot disagree about what the code is.
 *
 * Upper-cased and trimmed to match what the API stores; it normalises again on
 * its side, so this is convenience, not validation.
 */
export function promoCodeFrom(raw) {
  const value = String(raw ?? "").trim();
  const match = value.match(/\/gift\/([^/?#\s]+)/i);
  if (!match) {
    // A real code never contains a slash, so something slash-shaped that did
    // not match is a link with no code in it -- `/gift/` on its own, say.
    // Returning it verbatim would put "/GIFT/" in front of the customer as
    // though it were their code.
    return value.includes("/") ? "" : value.toUpperCase();
  }
  try {
    return decodeURIComponent(match[1]).trim().toUpperCase();
  } catch {
    // A stray percent sign is not worth failing over; the server will reject
    // the code on its own terms.
    return match[1].trim().toUpperCase();
  }
}

// -- clipboard ------------------------------------------------------------

/**
 * Copies text and reports it on the button itself.
 *
 * navigator.clipboard is unavailable on plain HTTP and in some in-app
 * browsers, so the selection fallback stays — a subscription link you cannot
 * copy is a subscription you cannot use.
 */
export async function copyText(text, button) {
  const done = () => {
    if (!button) return;
    const previous = button.getAttribute("aria-label");
    button.setAttribute("aria-label", "Скопировано");
    button.classList.add("accent");
    setTimeout(() => {
      button.setAttribute("aria-label", previous || "Копировать");
      button.classList.remove("accent");
    }, 1600);
  };

  try {
    await navigator.clipboard.writeText(text);
    done();
    return true;
  } catch {
    const scratch = el("textarea", { value: text, "aria-hidden": "true", class: "sr-only" });
    document.body.append(scratch);
    scratch.select();
    const ok = document.execCommand?.("copy");
    scratch.remove();
    if (ok) done();
    return Boolean(ok);
  }
}

// -- shared chrome --------------------------------------------------------

/** Marks the nav link matching the current path. */
export function markCurrentTab() {
  for (const link of $$("[data-tab]")) {
    const isCurrent = link.getAttribute("href") === location.pathname;
    if (isCurrent) link.setAttribute("aria-current", "page");
    else link.removeAttribute("aria-current");
  }
}

/** GET /api/config, fetched once per page load. */
let configPromise;
export function clientConfig() {
  configPromise ||= api("/api/config").catch(() => ({}));
  return configPromise;
}
