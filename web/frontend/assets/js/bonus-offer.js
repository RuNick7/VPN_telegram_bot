/*
 * The offer to connect the identity this account arrived without.
 *
 * Built rather than written into every page's markup, because it belongs to
 * none of them: it is about the account, and the four cabinet pages should not
 * each carry a copy of a dialog that is usually not shown.
 *
 * Two directions, depending on what is missing:
 *   - signed up by email  -> attach Telegram, using the existing link handshake
 *   - signed up in the bot -> confirm an address, which posts a letter
 *
 * Shown once per visit at most, never after it has been collected, and never
 * again after "больше не показывать" — which is recorded on the account rather
 * than in this browser, so the answer also holds in the bot. Being asked again
 * in a different window is the thing that turns an offer into nagging.
 */

import { $, api, ApiError, daysLabel, el, withBusy } from "./core.js";

const COPY = {
  telegram: {
    tag: "Бонус",
    title: "Привяжите Telegram",
    lead: (days) =>
      `Получите ещё ${daysLabel(days)} подписки. Telegram — это второй способ войти: ` +
      `если доступ к почте пропадёт, аккаунт останется у вас.`,
    action: "Привязать Telegram",
  },
  email: {
    tag: "Бонус",
    title: "Добавьте почту",
    lead: (days) =>
      `Получите ещё ${daysLabel(days)} подписки. Почта — это второй способ войти: ` +
      `если Telegram окажется недоступен, аккаунт останется у вас.`,
    action: "Отправить письмо",
  },
};

/** Builds the dialog. Nothing is inserted until there is something to offer. */
function buildDialog(kind, days) {
  const copy = COPY[kind];
  const dialog = el("dialog", { class: "modal", "aria-labelledby": "bonus-title" });

  const status = el("p", { class: "mono-sm muted" });
  status.hidden = true;

  const field = el("input", {
    class: "input",
    id: "bonus-email",
    type: "email",
    inputmode: "email",
    autocomplete: "email",
    spellcheck: "false",
    placeholder: "mail@example.com",
  });

  const emailField = el("div", { class: "field" }, [
    el("label", { for: "bonus-email", text: "Ваш адрес" }),
    field,
  ]);

  const primary = el("button", { class: "btn", type: "button", text: copy.action });
  const later = el("button", { class: "btn btn-ghost btn-sm", type: "button", text: "Не сейчас" });
  const stop = el("input", { type: "checkbox", id: "bonus-stop" });

  dialog.append(
    el("div", { class: "modal-body" }, [
      el("span", { class: "section-tag", text: copy.tag }),
      el("h2", { class: "h-md", id: "bonus-title", text: copy.title }),
      el("p", { class: "mono-sm muted", text: copy.lead(days) }),
      kind === "email" ? emailField : null,
      status,
      el("div", { class: "actions" }, [primary]),
    ]),
    el("div", { class: "modal-foot" }, [
      el("label", { class: "check", for: "bonus-stop" }, [
        stop,
        el("span", { text: "Больше не показывать" }),
      ]),
      later,
    ])
  );

  return { dialog, primary, later, stop, field, status };
}

function say(status, message, ok = false) {
  status.textContent = message;
  status.className = ok ? "mono-sm accent" : "mono-sm muted";
  status.hidden = false;
}

/** Records the refusal only when the box is ticked; closing is not refusing. */
async function close({ dialog, stop }) {
  if (stop.checked) {
    try {
      await api("/api/bonus/dismiss", { method: "POST" });
    } catch (err) {
      console.error("dismiss", err);
    }
  }
  dialog.close();
  dialog.remove();
}

async function attachTelegram(parts) {
  await withBusy(parts.primary, async () => {
    try {
      const link = await api("/api/link/telegram", { method: "POST" });
      // Opened rather than only shown: on a phone this hands straight over to
      // the Telegram app, which is the whole point of the deep link.
      window.open(link.url, "_blank", "noopener");
      say(parts.status, "Откройте бота и нажмите «Start» — дни начислим сразу.", true);
      parts.primary.textContent = "Открыть ещё раз";
    } catch (err) {
      say(parts.status, err instanceof ApiError ? err.message : "Не удалось создать ссылку.");
    }
  });
}

async function confirmEmail(parts) {
  const email = parts.field.value.trim();
  if (!email.includes("@")) {
    parts.field.setAttribute("aria-invalid", "true");
    say(parts.status, "Проверьте адрес почты.");
    return;
  }
  parts.field.removeAttribute("aria-invalid");

  await withBusy(parts.primary, async () => {
    try {
      const sent = await api("/api/me/email/confirm-request", {
        method: "POST",
        body: { email },
      });
      say(parts.status, `Письмо отправлено на ${sent.email}. Откройте ссылку из него.`, true);
      parts.primary.textContent = "Отправить ещё раз";
    } catch (err) {
      say(parts.status, err instanceof ApiError ? err.message : "Не удалось отправить письмо.");
    }
  });
}

/**
 * Shows the offer if this account has one waiting.
 *
 * Never throws into the page it decorates: a cabinet that failed to render an
 * optional dialog is still a working cabinet, and a rejected promise here
 * would land in `guarded` and blank the page behind it.
 */
export async function maybeOfferBonus() {
  try {
    const offer = await api("/api/bonus/offer");
    if (!offer.kind || offer.days <= 0) return;

    const parts = buildDialog(offer.kind, offer.days);
    document.body.append(parts.dialog);

    parts.primary.addEventListener("click", () =>
      offer.kind === "telegram" ? attachTelegram(parts) : confirmEmail(parts)
    );
    parts.later.addEventListener("click", () => close(parts));
    // Escape and the backdrop both count as "not now", and the checkbox is
    // read the same way whichever of the three closed it.
    parts.dialog.addEventListener("cancel", (event) => {
      event.preventDefault();
      close(parts);
    });

    parts.dialog.showModal();
  } catch (err) {
    console.error("bonus offer", err);
  }
}
