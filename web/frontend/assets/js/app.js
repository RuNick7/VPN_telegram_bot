/*
 * The cabinet shell: everything the four signed-in pages share.
 *
 * Each page ships its own header and tab bar as real markup rather than having
 * this build them, so the chrome is on screen before any script runs and a
 * failed module leaves a page you can still navigate out of.
 */

import { $, $$, api, guarded, icon, markCurrentTab, setText, clientConfig } from "./core.js";
import { maybeOfferBonus } from "./bonus-offer.js";

/** The signed-in user, fetched once and shared by the page's modules. */
let mePromise;
export function me() {
  mePromise ||= api("/api/me");
  return mePromise;
}

/** Fills the header identity block. */
async function fillIdentity() {
  const user = await me();
  setText("[data-me-email]", user.email || "Почта не указана");
  const tag = $("[data-me-tag]");
  if (tag) {
    tag.textContent = user.telegram_tag ? "@" + user.telegram_tag : "";
    tag.hidden = !user.telegram_tag;
  }
  return user;
}

function wireLogout() {
  for (const button of $$("[data-logout]")) {
    button.addEventListener("click", async () => {
      // The redirect happens either way. A logout that failed server-side has
      // still cleared the cookie, and leaving the user on a page that now
      // 401s on every call would be worse than sending them to the front.
      try {
        await api("/api/auth/logout", { method: "POST" });
      } catch (err) {
        console.error("logout", err);
      }
      location.replace("/");
    });
  }
}

/** Puts an icon into every `<span data-icon="name">` placeholder. */
export function hydrateIcons(root = document) {
  for (const slot of $$("[data-icon]", root)) {
    if (slot.firstChild) continue;
    slot.append(icon(slot.dataset.icon, slot.dataset.iconClass || ""));
  }
}

/**
 * Boots a cabinet page.
 *
 * `run` receives the user, so a page never fetches /api/me a second time.
 * Anything it throws lands in `guarded`, which turns a 401 into a redirect to
 * sign-in instead of an error message about a session the user cannot see.
 */
export function boot(run) {
  markCurrentTab();
  hydrateIcons();
  wireLogout();
  guarded(async () => {
    const user = await fillIdentity();
    await run(user);
    // After the page it interrupts has finished drawing. A dialog that opens
    // over a half-rendered cabinet reads as an error, and this one is only
    // ever an offer.
    await maybeOfferBonus();
  });
}

export { clientConfig };
