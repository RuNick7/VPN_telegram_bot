/*
 * The site as an app on the home screen.
 *
 * Registers the service worker (/sw.js, which says what it does and, more to
 * the point, what it leaves alone), and drives the "install" card on the
 * overview page when there is one.
 *
 * The card has two forms, because the platforms do:
 *
 *  - Chromium (Android, desktop Chrome/Edge/Yandex) fires
 *    `beforeinstallprompt`, and the button replays it.
 *  - iOS has no such event, ever. Installing is Share → «На экран „Домой“»,
 *    so the card says that instead of offering a button that cannot work.
 *
 * The browser's own install banner is suppressed only on a page that has the
 * card to replace it. Everywhere else it is left as the browser shows it.
 */

import { $, show } from "./core.js";

if ("serviceWorker" in navigator) {
  // A failed registration costs the offline page and the install prompt, not
  // the site, so it is not worth a message to the customer.
  navigator.serviceWorker.register("/sw.js").catch(() => {});

  // Signed-in pages only, and once per visit: see push.js. Loaded on demand
  // so the landing page never fetches it.
  if (location.pathname.startsWith("/app") && !visited()) {
    import("./push.js").then((push) => push.syncSubscription()).catch(() => {});
  }
}

function visited() {
  try {
    if (sessionStorage.getItem("push-synced")) return true;
    sessionStorage.setItem("push-synced", "1");
  } catch {
    // Storage blocked: sync on every page then, which is merely wasteful.
  }
  return false;
}

function isStandalone(win = window) {
  return win.matchMedia?.("(display-mode: standalone)").matches || win.navigator.standalone === true;
}

function isIOS(nav = navigator) {
  // iPadOS reports itself as a Mac; the touch points give it away.
  return /iphone|ipad|ipod/i.test(nav.userAgent) || (nav.platform === "MacIntel" && nav.maxTouchPoints > 1);
}

const card = $("[data-install]");
if (card && !isStandalone()) {
  const button = $("[data-install-button]", card);
  const iosHint = $("[data-install-ios]", card);
  let deferred = null;

  window.addEventListener("beforeinstallprompt", (event) => {
    event.preventDefault();
    deferred = event;
    show(button);
    show(card);
  });

  button?.addEventListener("click", async () => {
    if (!deferred) return;
    const prompt = deferred;
    deferred = null;
    await prompt.prompt();
    await prompt.userChoice.catch(() => null);
    // The event is single-use either way: accepted, it is installed; refused,
    // the browser will fire a fresh one when it is willing to ask again.
    show(card, false);
  });

  window.addEventListener("appinstalled", () => show(card, false));

  if (isIOS()) {
    show(iosHint);
    show(card);
  }
}
