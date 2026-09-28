/*
 * Redeems the link that binds an email address to an account.
 *
 * Reached from a letter, which means routinely on a device that has never
 * signed in — so this page proves nothing about the visitor and does not try
 * to. The token names the account; opening it is the proof.
 *
 * Same handling of the token as verify.js: it arrives in the query string,
 * which is the hardest place to keep a credential, so it is taken out of the
 * URL before anything else happens.
 */

import { $, api, ApiError, daysLabel, show } from "./core.js";

const token = new URLSearchParams(location.search).get("token") || "";

// Before the network call, not after: if the request hangs, the token is
// already gone from anything the visitor might copy out of the address bar.
history.replaceState(null, "", location.pathname);

function fail(message) {
  show($("[data-working]"), false);
  show($("[data-failed]"), true);
  $("[data-reason]").textContent = message;
  show($("[data-retry]"), true);
}

function succeed(result) {
  show($("[data-working]"), false);
  show($("[data-done]"), true);
  $("[data-address]").textContent =
    `${result.email} — теперь по этому адресу можно входить на сайт.`;

  // The plaque only appears when days were actually credited. Confirming a
  // second address is a perfectly good thing to do and pays nothing, and a
  // "0 дн. начислено" would read as a failure rather than as nothing owed.
  if (result.bonus_days > 0) {
    $("[data-bonus-days]").textContent = String(result.bonus_days);
    $("[data-bonus]").querySelector(".plaque-word").textContent =
      daysLabel(result.bonus_days).replace(/^\d+\s/, "") + " начислено";
    show($("[data-bonus]"), true);
  }
  show($("[data-cabinet]"), true);
}

if (!token) {
  fail("В ссылке нет кода подтверждения. Похоже, адрес скопирован не целиком.");
} else {
  try {
    succeed(await api("/api/auth/confirm-email", { method: "POST", body: { token } }));
  } catch (err) {
    fail(
      err instanceof ApiError
        ? err.message
        : "Не удалось подтвердить адрес. Запросите новое письмо."
    );
  }
}
