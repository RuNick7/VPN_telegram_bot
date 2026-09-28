/*
 * Redeems a magic link.
 *
 * The token arrives in the query string, which is the one place a credential
 * is hardest to keep: it is in the address bar, in history, and in the
 * Referer of anything the page loads afterwards. So it is taken out of the URL
 * before anything else happens, and never put anywhere else.
 */

import { $, api, ApiError, safePath } from "./core.js";

const params = new URLSearchParams(location.search);
const token = params.get("token") || "";
const next = safePath(params.get("next"), "/app");

// Rewrite the address bar immediately, before the network call. If the request
// hangs, the token is already gone from anything the user might copy or share.
history.replaceState(null, "", location.pathname);

function fail(message) {
  $("[data-working]").hidden = true;
  $("[data-failed]").hidden = false;
  $("[data-reason]").textContent = message;
  $("[data-retry]").hidden = false;
}

if (!token) {
  fail("В ссылке нет кода подтверждения. Похоже, адрес скопирован не целиком.");
} else {
  try {
    await api("/api/auth/verify", { method: "POST", body: { token } });
    // replace, not assign: the back button should not return to a spent link.
    location.replace(next);
  } catch (err) {
    fail(
      err instanceof ApiError
        ? err.message
        : "Не удалось проверить ссылку. Попробуйте запросить новую."
    );
  }
}
