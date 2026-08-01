/*
 * Profile: how you sign in, who invited you, and what we have published.
 *
 * Two fields here are one-way. The referrer can be named once and never
 * changed, and the Telegram link, once made, merges two accounts into one.
 * Both are rendered as permanently settled once they are set, rather than as
 * an edit that will be refused server-side.
 */

import { boot, hydrateIcons, clientConfig } from "./app.js";
import {
  $,
  $$,
  api,
  ApiError,
  copyText,
  flash,
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
      flash("Адрес сохранён. Следующая ссылка для входа придёт на него.", "ok");
    } catch (err) {
      flash(err instanceof ApiError ? err.message : "Не удалось сохранить адрес.");
    }
  });
}

// -- telegram -------------------------------------------------------------

function renderLinkState(status) {
  const note = $("[data-tg-note]");

  if (status.linked) {
    $("[data-tg-linked]").hidden = false;
    $("[data-tg-unlinked]").hidden = true;
    $("[data-tg-tag]").textContent = status.telegram_tag ? "@" + status.telegram_tag : "Аккаунт привязан";
    note.textContent = "Вход через Telegram работает наравне с почтой.";
    return;
  }

  $("[data-tg-linked]").hidden = true;
  if (!status.can_link) {
    // Nothing to offer, so nothing is shown that would fail on click.
    note.textContent = "Привязка Telegram сейчас не настроена.";
    return;
  }
  $("[data-tg-unlinked]").hidden = false;
  note.textContent = status.link_pending
    ? "Ссылка уже создана и ждёт подтверждения в боте."
    : "Telegram не привязан.";
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

  const own = $("[data-ref-own]");
  own.textContent = referrals.own_tag ? "@" + referrals.own_tag : "—";
  $("[data-ref-own-note]").textContent = referrals.own_tag
    ? "Его называют те, кого вы пригласили."
    : "Появится после привязки Telegram — приглашения считаются по нику.";

  if (referrals.referrer_locked) {
    $("[data-ref-set]").hidden = false;
    $("[data-ref-referrer]").textContent = "@" + referrals.referrer_tag;
  } else {
    $("[data-ref-form]").hidden = false;
  }
}

async function saveReferrer(event) {
  event.preventDefault();
  clearFlash();

  const input = $("#referrer");
  const tag = input.value.trim().replace(/^@/, "");
  if (!tag) {
    input.setAttribute("aria-invalid", "true");
    flash("Укажите ник пригласившего.");
    return;
  }
  input.removeAttribute("aria-invalid");

  await withBusy($("[data-ref-submit]"), async () => {
    try {
      const result = await api("/api/referrals/referrer", { method: "PUT", body: { tag } });
      $("[data-ref-form]").hidden = true;
      $("[data-ref-set]").hidden = false;
      $("[data-ref-referrer]").textContent = "@" + result.referrer_tag;
      flash(result.detail || "Пригласивший сохранён.", "ok");
    } catch (err) {
      flash(err instanceof ApiError ? err.message : "Не удалось сохранить.");
    }
  });
}

// -- docs -----------------------------------------------------------------

function renderDocs(config) {
  let published = 0;
  for (const link of $$("[data-doc]")) {
    const url = config.docs?.[link.dataset.doc];
    if (!url) {
      link.closest("li")?.remove();
      continue;
    }
    link.href = url;
    link.rel = "noopener";
    link.target = "_blank";
    link.hidden = false;
    published += 1;
  }
  $("[data-doc-empty]").hidden = published > 0;

  const support = $("[data-support]");
  if (config.support_url) {
    support.href = config.support_url;
    support.hidden = false;
  }
}

// -- boot -----------------------------------------------------------------

boot(async (user) => {
  $("#email").value = user.email || "";
  $("[data-email-form]").addEventListener("submit", saveEmail);
  $("[data-ref-form]").addEventListener("submit", saveReferrer);
  $("[data-tg-link]").addEventListener("click", createLink);
  $("[data-tg-copy]").addEventListener("click", (event) =>
    copyText($("[data-tg-link-url]").value, event.currentTarget)
  );

  clientConfig().then(renderDocs);

  const [linkStatus, referrals] = await Promise.all([
    api("/api/link/telegram"),
    api("/api/referrals"),
  ]);
  renderLinkState(linkStatus);
  renderReferrals(referrals);
  hydrateIcons();
});
