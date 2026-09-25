/*
 * Sign-in.
 *
 * Email is the whole login route; Telegram is an alternative that only appears
 * when the server says a bot is configured. There is no password field to
 * strengthen, no reset flow to abuse, and nothing on this page that reveals
 * whether an address has an account -- the API answers the same either way, and
 * so does the copy below.
 */

import { $, api, ApiError, clientConfig, el, flash, clearFlash, safePath, withBusy } from "./core.js";

const form = $("[data-email-form]");
const sent = $("[data-sent]");
const input = $("#email");

/** Where to land after signing in. Comes from the URL, so it is not trusted. */
function nextPath() {
  return safePath(new URLSearchParams(location.search).get("next"), "/app");
}

/**
 * Reports a failed Telegram sign-in.
 *
 * The callback redirects here with a code rather than a message, so the
 * wording lives in this file. Reflecting text out of a query string would be a
 * way to put arbitrary words in front of someone under our own domain.
 */
function reportCallbackError() {
  const reason = new URLSearchParams(location.search).get("error");
  if (!reason) return;
  history.replaceState(null, "", location.pathname);

  const messages = {
    bad_signature: "Данные Telegram не прошли проверку. Попробуйте войти ещё раз.",
    no_account:
      "Не удалось открыть аккаунт. Попробуйте ещё раз или войдите по почте.",
    not_configured: "Вход через Telegram сейчас не настроен. Используйте почту.",
  };
  flash(messages[reason] || "Не удалось войти через Telegram. Попробуйте почту.");
}

reportCallbackError();

// Someone who is already signed in has no business on this page; send them on
// rather than making them submit a form to be told so.
api("/api/me")
  .then(() => location.replace(nextPath()))
  .catch(() => {});

form?.addEventListener("submit", async (event) => {
  event.preventDefault();
  clearFlash();

  const email = input.value.trim();
  if (!email || !email.includes("@")) {
    input.setAttribute("aria-invalid", "true");
    flash("Проверьте адрес почты.");
    input.focus();
    return;
  }
  input.removeAttribute("aria-invalid");

  await withBusy($("[data-submit]"), async () => {
    try {
      const result = await api("/api/auth/magic-link", { method: "POST", body: { email } });
      form.hidden = true;
      sent.hidden = false;
      $("[data-sent-detail]").textContent = result.detail || "Ссылка отправлена.";
    } catch (err) {
      flash(err instanceof ApiError ? err.message : "Не удалось отправить письмо.");
    }
  });
});

$("[data-again]")?.addEventListener("click", () => {
  sent.hidden = true;
  form.hidden = false;
  clearFlash();
  input.focus();
});

// -- Telegram -------------------------------------------------------------

/**
 * Wires our own button to Telegram's login script.
 *
 * The widget's own markup is a fixed blue pill inside a cross-origin iframe:
 * unstyleable from here, and the one element on the site that looked borrowed
 * from somewhere else. `Telegram.Login.auth` is the same entry point the pill
 * calls, so what changes is only what the customer clicks.
 *
 * This is the callback form, but invoked from a module we serve rather than
 * from a `data-onauth` attribute -- the attribute is what would have needed
 * 'unsafe-eval' in the policy, not the function.
 *
 * The payload goes to POST /api/auth/telegram, which verifies its HMAC before
 * issuing anything. Nothing here is trusted; the browser only carries it.
 */
function mountTelegram(botID) {
  const button = $("[data-telegram-login]");
  if (!button) return;

  const script = el("script", {
    async: true,
    src: "https://telegram.org/js/telegram-widget.js?22",
  });
  script.addEventListener("load", () => {
    $("[data-telegram-block]").hidden = false;
  });
  script.addEventListener("error", () => {
    // telegram.org unreachable -- blocked, offline, an extension. Say so
    // rather than leaving a button that silently does nothing.
    flash("Не удалось загрузить вход через Telegram. Войдите по почте.");
  });
  document.head.append(script);

  button.addEventListener("click", () => {
    const login = window.Telegram?.Login;
    if (!login) {
      flash("Вход через Telegram сейчас недоступен. Войдите по почте.");
      return;
    }
    withBusy(button, () => new Promise((resolve) => {
      login.auth({ bot_id: botID, request_access: "write" }, async (payload) => {
        if (!payload) {
          // The customer closed the window or declined. Not an error.
          resolve();
          return;
        }
        try {
          await api("/api/auth/telegram", { method: "POST", body: payload });
          location.replace(nextPath());
        } catch (err) {
          flash(err instanceof ApiError ? err.message : "Не удалось войти через Telegram.");
        }
        resolve();
      });
    }));
  });
}

clientConfig().then((config) => {
  if (config.telegram_login && config.telegram_bot_id) {
    mountTelegram(String(config.telegram_bot_id));
  }
  // The agreement link in the sentence above the form is markup now, with a
  // real href, and assets/js/footer.js repoints it along with every other
  // [data-doc] on the page. It used to be hidden until this ran and matched
  // `[data-doc="license"]` by position -- which the footer's own agreement
  // link would have made ambiguous.
});
