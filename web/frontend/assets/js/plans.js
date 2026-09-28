/*
 * Tariffs, traffic packs, gifts and promo codes.
 *
 * Nothing here decides a price. Every button sends only *which* plan was
 * chosen; the server looks the amount up in its own table. A client that could
 * name its own amount could buy a year for a rouble, so the request body
 * deliberately has no room for one.
 *
 * Payment is also not confirmed here. Creating a payment returns a YooKassa URL
 * and nothing else; the subscription moves only when the Python webhook has
 * re-fetched the payment from YooKassa and credited it. That is why coming back
 * from the payment page polls instead of assuming.
 */

import { boot, hydrateIcons } from "./app.js";
import {
  $,
  api,
  ApiError,
  copyText,
  el,
  flash,
  clearFlash,
  formatRub,
  formatDate,
  daysLabel,
  icon,
  plural,
  promoCodeFrom,
  show,
  withBusy,
} from "./core.js";

let paymentsEnabled = true;

// -- buying ---------------------------------------------------------------

/**
 * Creates a payment and hands the browser to YooKassa.
 *
 * `return_url` is a path, never a full URL: the API refuses absolute ones, so
 * this endpoint cannot be turned into an open redirect that arrives wrapped in
 * a real payment flow.
 */
async function startPayment(button, endpoint, body) {
  await withBusy(button, async () => {
    clearFlash();
    try {
      const payment = await api(endpoint, {
        method: "POST",
        body: { ...body, return_url: "/app/plans?payment=pending" },
      });
      // assign, not replace: the back button should return here, not to a
      // payment form that has already been submitted.
      location.assign(payment.confirmation_url);
    } catch (err) {
      flash(err instanceof ApiError ? err.message : "Не удалось создать платёж.");
    }
  });
}

// -- rendering ------------------------------------------------------------

function planCard(plan, { gift }) {
  const button = el("button", {
    class: gift ? "btn btn-outline btn-block" : "btn btn-block",
    type: "button",
    disabled: !paymentsEnabled,
    onclick: (event) =>
      startPayment(
        event.currentTarget,
        gift ? "/api/payments/gift" : "/api/payments/subscription",
        { months: plan.months }
      ),
    text: gift ? "Подарить" : "Оплатить",
  });

  return el("div", { class: "plan", "data-best": !gift && plan.discount >= 20 }, [
    el("div", { class: "stack" }, [
      el("span", { class: "mono-sm muted", text: plan.label }),
      el("div", { class: "metric num", text: formatRub(plan.price) }),
      plan.discount > 0 ? el("span", { class: "badge", text: `−${plan.discount}%` }) : null,
      el("span", {
        class: "mono-sm muted",
        text: `${plan.days} ${plural(plan.days, "день", "дня", "дней")}`,
      }),
    ]),
    button,
  ]);
}

function packCard(pack, label) {
  return el("div", { class: "plan" }, [
    el("div", { class: "stack" }, [
      el("span", { class: "mono-sm muted", text: label }),
      el("div", { class: "metric num", text: `${pack.gigabytes} ГБ` }),
      pack.discount > 0 ? el("span", { class: "badge", text: `−${pack.discount}%` }) : null,
      el("span", { class: "mono-sm strong num", text: formatRub(pack.price) }),
    ]),
    el("button", {
      class: "btn btn-block",
      type: "button",
      disabled: !paymentsEnabled,
      onclick: (event) =>
        startPayment(event.currentTarget, "/api/payments/traffic", { gigabytes: pack.gigabytes }),
      text: "Купить",
    }),
  ]);
}

function fill(host, nodes) {
  host.textContent = "";
  for (const node of nodes) host.append(node);
}

// -- promo ----------------------------------------------------------------

async function redeemPromo(event) {
  event.preventDefault();
  clearFlash();

  const input = $("#promo");
  const code = promoCodeFrom(input.value);
  if (!code) {
    input.setAttribute("aria-invalid", "true");
    flash("Введите промокод.");
    return;
  }
  input.removeAttribute("aria-invalid");

  await withBusy($("[data-promo-submit]"), async () => {
    try {
      const result = await api("/api/promo/redeem", { method: "POST", body: { code } });
      input.value = "";
      flash(
        `Готово: ${daysLabel(result.days_added)} добавлено. Подписка активна до ${formatDate(result.expires_at)}.`,
        "ok"
      );
    } catch (err) {
      flash(err instanceof ApiError ? err.message : "Не удалось активировать код.");
    }
  });
}

// -- gifts already bought -------------------------------------------------

/** A read-only field with a copy button beside it. */
function copyRow(label, value) {
  const field = el("input", {
    type: "text",
    readonly: true,
    value,
    "aria-label": label,
    spellcheck: "false",
  });
  const button = el("button", { type: "button", "aria-label": `Копировать ${label}` });
  button.append(icon("copy"));
  button.addEventListener("click", () => copyText(value, button));
  return el("div", { class: "copy" }, [field, button]);
}

function giftRow(gift) {
  const redeemed = Boolean(gift.redeemed_at);
  const badge = el("span", {
    class: "badge",
    "data-kind": redeemed ? "off" : "on",
    text: redeemed ? `Активирован ${formatDate(gift.redeemed_at)}` : "Ждёт активации",
  });

  return el("li", { class: "gift", "data-redeemed": redeemed }, [
    el("div", { class: "row between wrap-row" }, [
      el("span", { class: "mono strong", text: daysLabel(gift.days) }),
      badge,
    ]),
    // A redeemed gift keeps its code on screen but loses the fields: the code
    // is how you recognise which gift was used, and handing out a spent one
    // helps nobody.
    redeemed
      ? el("span", { class: "mono-sm muted", text: gift.code })
      : copyRow("код", gift.code),
    !redeemed && gift.link ? copyRow("ссылку", gift.link) : null,
  ]);
}

/**
 * Draws the gifts this account has paid for.
 *
 * The only place a buyer without Telegram can reach them: the bot's message
 * goes to an account they do not have, and until this existed the code was
 * charged for and then shown nowhere.
 */
function renderGifts(gifts) {
  const list = $("[data-gift-list]");
  if (!list) return 0;
  list.textContent = "";
  for (const gift of gifts) list.append(giftRow(gift));
  show($("[data-my-gifts]"), gifts.length > 0);
  return gifts.length;
}

async function loadGifts() {
  try {
    const result = await api("/api/gifts");
    return renderGifts(result.gifts || []);
  } catch (err) {
    // A failure here must not blank the page somebody came to buy on.
    console.error("gifts", err);
    return 0;
  }
}

// -- returning from YooKassa ---------------------------------------------

/**
 * Tells the user what happened after they come back from the payment page.
 *
 * Crediting is asynchronous by design -- only the webhook may move a payment
 * out of pending, because only it re-fetches the payment from YooKassa first --
 * so the honest answer while that is in flight is "we are waiting", not
 * "paid". Nothing here changes any state; it only reads.
 */
async function reportReturn(giftsBefore) {
  const params = new URLSearchParams(location.search);
  if (!params.has("payment")) return;
  history.replaceState(null, "", location.pathname + location.hash);

  flash("Платёж принят. Начисляем — обычно это занимает несколько секунд.", "ok");

  for (let attempt = 0; attempt < 6; attempt += 1) {
    await new Promise((resolve) => setTimeout(resolve, 2500));
    try {
      // Both, because a gift never moves the buyer's own subscription. Waiting
      // only on that told a gift buyer their payment had not gone through, and
      // then sent them to support -- for a purchase that had worked perfectly.
      const [subscription, gifts] = await Promise.all([
        api("/api/subscription"),
        loadGifts(),
      ]);
      if (gifts > giftsBefore) {
        flash("Подарок готов — код и ссылка ниже, в разделе «Подарок».", "ok");
        $("[data-my-gifts]")?.scrollIntoView({ block: "center" });
        return;
      }
      if (subscription.active) {
        flash(`Подписка активна до ${formatDate(subscription.expires_at)}.`, "ok");
        return;
      }
    } catch {
      // Keep waiting: a transient read failure says nothing about the payment.
    }
  }
  flash(
    "Платёж обрабатывается. Если ничего не изменится в течение получаса, напишите в поддержку.",
    "ok"
  );
}

/**
 * Scrolls to the section named in the URL, once it exists.
 *
 * The browser acts on `#traffic` the moment the document loads, and at that
 * moment the traffic section is still `hidden` -- it is revealed only after
 * /api/plans answers with the packs to put in it. A hidden element is not a
 * scroll target, so the jump silently did nothing and "Купить гигабайты"
 * landed the customer at the top of the tariffs to hunt for it.
 *
 * Runs after rendering rather than on a timer: by here the section either
 * exists or genuinely is not offered.
 */
function revealRequestedSection() {
  const id = location.hash.slice(1);
  if (!id) return;
  const target = document.getElementById(id);
  // `hidden` covers the section being switched off entirely -- traffic when
  // quotas are disabled. Scrolling to nothing is worse than staying put.
  if (!target || target.hidden) return;
  target.scrollIntoView({ block: "start", behavior: "smooth" });
}

// -- boot -----------------------------------------------------------------

boot(async () => {
  $("[data-promo-form]")?.addEventListener("submit", redeemPromo);

  const plans = await api("/api/plans");
  paymentsEnabled = Boolean(plans.payments_enabled);
  $("[data-payments-off]").hidden = paymentsEnabled;

  fill(
    $("[data-plans]"),
    plans.plans.map((plan) => planCard(plan, { gift: false }))
  );
  fill(
    $("[data-gifts]"),
    plans.plans.map((plan) => planCard(plan, { gift: true }))
  );

  const tierNote = $("[data-tier-note]");
  if (plans.tier > 0) {
    tierNote.textContent =
      `Цены с учётом вашего уровня скидки ${plans.tier}: приглашено ${plans.referred_people} ${plural(plans.referred_people, "человек", "человека", "человек")}.`;
  } else {
    tierNote.textContent =
      "Базовые цены. Пригласите друга — со следующего уровня подписка станет дешевле.";
  }

  if (plans.traffic_packs?.length) {
    $("[data-traffic-section]").hidden = false;
    $("[data-traffic-label]").textContent = plans.traffic_label || "Трафик";
    fill(
      $("[data-packs]"),
      plans.traffic_packs.map((pack) => packCard(pack, plans.traffic_label || "Пакет"))
    );
  }

  hydrateIcons();
  revealRequestedSection();
  // Counted before polling starts, so "a gift appeared" means this payment's
  // gift rather than one bought last week.
  reportReturn(await loadGifts());
});
