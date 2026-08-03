/*
 * Profile: how you sign in, who invited you, and what we have published.
 *
 * Two fields here are one-way. The referrer can be named once and never
 * changed, and the Telegram link, once made, merges two accounts into one.
 * Both are rendered as permanently settled once they are set, rather than as
 * an edit that will be refused server-side.
 */

import { boot, hydrateIcons } from "./app.js";
import {
  $,
  api,
  ApiError,
  copyText,
  flash,
  show,
  clearFlash,
  withBusy,
} from "./core.js";

// -- email ----------------------------------------------------------------

async function saveEmail(event) {
  event.preventDefault();
  clearFlash();

  const input = $("#email");
  const email = input.value.trim();
  if (!email.includes("@")) {
    input.setAttribute("aria-invalid", "true");
    flash("Проверьте адрес почты.");
    return;
  }
  input.removeAttribute("aria-invalid");

  await withBusy($("[data-email-submit]"), async () => {
    try {
      const result = await api("/api/me/email", { method: "PATCH", body: { email } });
      input.value = result.email;
      $("[data-me-email]").textContent = result.email;
      flash("Адрес изменён. Следующая ссылка для входа придёт на него.", "ok");
    } catch (err) {
      flash(err instanceof ApiError ? err.message : "Не удалось изменить адрес.");
    }
  });
}

// -- telegram -------------------------------------------------------------

function renderLinkState(status) {
  const note = $("[data-tg-note]");
  const linked = $("[data-tg-linked]");
  const unlinked = $("[data-tg-unlinked]");

  if (status.linked) {
    linked.hidden = false;
    unlinked.hidden = true;
    $("[data-tg-tag]").value = status.telegram_tag
      ? "@" + status.telegram_tag
      : "Аккаунт привязан";
    // Unlinking leaves the address as the only way in, so it is not offered
    // to an account that has none. The server refuses it too; this is so the
    // button is not there to be pressed rather than there to fail.
    show($("[data-tg-unlink]"), Boolean(status.can_unlink));
    note.textContent = status.can_unlink
      ? "Вход через Telegram работает наравне с почтой."
      : "Вход через Telegram работает наравне с почтой. Добавьте почту, чтобы можно было отвязать.";
    return;
  }

  linked.hidden = true;
  if (!status.can_link) {
    // Nothing to offer, so nothing is shown that would fail on click.
    note.textContent = "Привязка Telegram сейчас не настроена.";
    return;
  }
  unlinked.hidden = false;
  note.textContent = status.link_pending
    ? "Ссылка уже создана и ждёт подтверждения в боте."
    : "Telegram не привязан.";
}

async function unlinkTelegram(event) {
  const confirmed = confirm(
    "Отвязать Telegram?\n\n" +
      "Войти на сайт можно будет только по почте, а в боте этот аккаунт станет новым — " +
      "подписка, трафик и приглашённые останутся здесь.\n\n" +
      "Привязать другой Telegram можно сразу после этого."
  );
  if (!confirmed) return;

  await withBusy(event.currentTarget, async () => {
    clearFlash();
    try {
      renderLinkState(await api("/api/link/telegram", { method: "DELETE" }));
      $("[data-me-tag]").hidden = true;
      flash("Telegram отвязан. Можно привязать другой.", "ok");
    } catch (err) {
      flash(err instanceof ApiError ? err.message : "Не удалось отвязать Telegram.");
    }
  });
}

async function createLink(event) {
  await withBusy(event.currentTarget, async () => {
    clearFlash();
    try {
      const link = await api("/api/link/telegram", { method: "POST" });
      const box = $("[data-tg-link-box]");
      $("[data-tg-link-url]").value = link.url;
      box.hidden = false;

      const hint = $("[data-tg-link-hint]");
      const minutes = Math.max(1, Math.round((link.expires_in || 900) / 60));
      hint.textContent = `${link.detail} Ссылка действует ${minutes} мин.`;
      hint.hidden = false;

      // Opened rather than only shown: on a phone this hands straight over to
      // the Telegram app, which is the whole point of the deep link.
      window.open(link.url, "_blank", "noopener");
    } catch (err) {
      flash(err instanceof ApiError ? err.message : "Не удалось создать ссылку.");
    }
  });
}

// -- referrals ------------------------------------------------------------

function renderReferrals(referrals) {
  $("[data-ref-count]").textContent = String(referrals.referred_people ?? 0);
  $("[data-ref-tier]").textContent =
    referrals.tier >= referrals.max_tier
      ? "Максимальный уровень"
      : `Уровень ${referrals.tier} из ${referrals.max_tier}`;

  // What this user is named by when they invite somebody. A Telegram tag if
  // they have one, otherwise their address — which the referrer field now
  // accepts, so an account with no Telegram is no longer un-nameable.
  const own = $("[data-ref-own]");
  own.textContent = referrals.own_tag ? "@" + referrals.own_tag : referrals.own_email || "—";
  $("[data-ref-own-note]").textContent = referrals.own_tag
    ? "Его называют те, кого вы пригласили."
    : referrals.own_email
      ? "Этот адрес называют те, кого вы пригласили. Привяжите Telegram, чтобы вас находили и по нику."
      : "Укажите почту или привяжите Telegram, чтобы вас можно было указать как пригласившего.";

  if (referrals.referrer_locked) {
    $("[data-ref-set]").hidden = false;
    $("[data-ref-referrer]").textContent = referrerLabel(referrals.referrer_tag);
  } else {
    $("[data-ref-form]").hidden = false;
  }
}

/** An address is shown as typed; a Telegram tag gets its `@` back. */
function referrerLabel(handle) {
  const value = String(handle || "");
  return value.includes("@") ? value : "@" + value;
}

async function saveReferrer(event) {
  event.preventDefault();
  clearFlash();

  const input = $("#referrer");
  // A tag loses its `@`; an address keeps everything after the first one. The
  // server normalises again on its side, so this is only about not sending an
  // address with the leading `@` a customer typed out of habit.
  const raw = input.value.trim();
  const tag = raw.replace(/^@/, "");
  if (!tag) {
    input.setAttribute("aria-invalid", "true");
    flash("Укажите ник или почту пригласившего.");
    return;
  }
  input.removeAttribute("aria-invalid");

  await withBusy($("[data-ref-submit]"), async () => {
    try {
      const result = await api("/api/referrals/referrer", { method: "PUT", body: { tag } });
      $("[data-ref-form]").hidden = true;
      $("[data-ref-set]").hidden = false;
      $("[data-ref-referrer]").textContent = referrerLabel(result.referrer_tag);
      flash(result.detail || "Пригласивший сохранён.", "ok");
    } catch (err) {
      flash(err instanceof ApiError ? err.message : "Не удалось сохранить.");
    }
  });
}

// -- boot -----------------------------------------------------------------

boot(async (user) => {
  $("#email").value = user.email || "";
  $("[data-email-form]").addEventListener("submit", saveEmail);
  $("[data-ref-form]").addEventListener("submit", saveReferrer);
  $("[data-tg-link]").addEventListener("click", createLink);
  $("[data-tg-unlink]").addEventListener("click", unlinkTelegram);
  $("[data-tg-copy]").addEventListener("click", (event) =>
    copyText($("[data-tg-link-url]").value, event.currentTarget)
  );

  const [linkStatus, referrals] = await Promise.all([
    api("/api/link/telegram"),
    api("/api/referrals"),
  ]);
  renderLinkState(linkStatus);
  renderReferrals(referrals);
  hydrateIcons();
});
