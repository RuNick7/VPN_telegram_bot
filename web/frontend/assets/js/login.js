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
 * Mounts Telegram's login widget in redirect mode.
 *
 * `data-auth-url` rather than `data-onauth`: the callback form has the widget
 * script evaluate an attribute string, which would mean allowing 'unsafe-eval'
 * in the page's Content-Security-Policy for one optional button. In redirect
 * mode Telegram sends the browser to our own endpoint with the signed payload
 * in the query string, and the signature is checked server-side either way.
 */
function mountTelegram(botUsername) {
  const host = $("[data-telegram-widget]");
  if (!host) return;

  const script = el("script", {
    async: true,
    src: "https://telegram.org/js/telegram-widget.js?22",
    "data-telegram-login": botUsername,
    "data-size": "large",
    "data-radius": "0",
    "data-userpic": "false",
    "data-auth-url": `${location.origin}/auth/telegram?next=${encodeURIComponent(nextPath())}`,
  });
  host.append(script);
  $("[data-telegram-block]").hidden = false;
}

clientConfig().then((config) => {
  if (config.telegram_login && config.telegram_bot) {
    mountTelegram(config.telegram_bot);
  }
  // The agreement link in the sentence above the form is markup now, with a
  // real href, and assets/js/footer.js repoints it along with every other
  // [data-doc] on the page. It used to be hidden until this ran and matched
  // `[data-doc="license"]` by position -- which the footer's own agreement
  // link would have made ambiguous.
});
