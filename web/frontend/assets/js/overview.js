/*
 * Cabinet overview.
 *
 * Four independent reads (subscription, traffic, devices, referrals). They are
 * issued together and rendered as they land, because three of them go through
 * to the Remnawave panel and one slow node should not hold up the page.
 */

import { boot } from "./app.js";
import {
  $,
  api,
  ApiError,
  copyText,
  daysLabel,
  el,
  flash,
  formatDate,
  formatGB,
  setText,
  show,
} from "./core.js";

// -- subscription ---------------------------------------------------------

/**
 * Renders the two states this page really has: with a subscription and
 * without one.
 *
 * Nothing is shown before the answer is known, and the "without" state offers
 * only the one thing that can be done from it. Showing "renew" or "connect a
 * device" to somebody with no subscription is offering an action that leads
 * to an empty page.
 */
function renderSubscription(sub) {
  const active = Boolean(sub.active);
  const url = sub.subscription_url || "";

  $("[data-status-dot]").dataset.off = String(!active);
  setText("[data-status-label]", active ? "Подписка активна" : "Подписки нет");

  const title = $("[data-status-title]");
  title.textContent = "";
  title.append(
    "Kaira ",
    el("br"),
    el("span", { class: active ? "accent" : "muted", text: active ? "Active" : "Offline" })
  );

  setText(
    "[data-status-note]",
    active
      ? "Доступ открыт. Подключайте устройства по ссылке подписки — она одна на всех."
      : "Доступ закрыт. Оформите подписку, чтобы начать пользоваться."
  );

  show($("[data-side]"), true);
  show($("[data-has-subscription]"), active);
  show($("[data-actions-active]"), active);
  show($("[data-actions-none]"), !active);

  if (active) {
    // `tier` is the squad the account sits in, which is what actually decides
    // what it can reach — not what was last paid for.
    const names = { free: "Бесплатный", lte: "С квотой трафика" };
    setText("[data-plan-name]", names[sub.tier] || "Полный доступ");
    setText("[data-plan-until]", formatDate(sub.expires_at));
    setText("[data-plan-left]", `Осталось: ${daysLabel(sub.days_left)}`);
  }

  // The link section appears only when there is a link. An empty field that
  // takes focus when clicked reads as something that should have had a value.
  show($("[data-sub-section]"), Boolean(url));
  const field = $("[data-sub-url]");
  if (field) field.value = url;
}

// -- traffic --------------------------------------------------------------

function renderTraffic(traffic) {
  if (!traffic?.enabled) return;

  const cell = $("[data-traffic-cell]");
  cell.hidden = false;
  setText("[data-traffic-label]", traffic.label || "Трафик");

  const total = (traffic.free_bytes || 0) + (traffic.purchased_bytes || 0);
  const remaining = Math.max(0, traffic.remaining_bytes || 0);
  const used = Math.max(0, total - remaining);

  setText("[data-traffic-used]", formatGB(used));
  setText("[data-traffic-total]", `/ ${formatGB(total)} ГБ`);

  const share = total > 0 ? Math.min(100, (used / total) * 100) : 0;
  const meter = $("[data-traffic-meter]");
  meter.dataset.low = String(total > 0 && remaining / total < 0.15);
  // Written through the CSSOM rather than as a `style` attribute in markup:
  // the former is not what `style-src` polices, so the strict CSP holds.
  meter.firstElementChild.style.width = share.toFixed(1) + "%";

  const parts = [`Осталось ${formatGB(remaining)} ГБ`];
  if (traffic.cycle_ends_at) parts.push(`обновится ${formatDate(traffic.cycle_ends_at)}`);
  if (!traffic.available) parts.push("расходуется только при активной подписке");
  setText("[data-traffic-note]", parts.join(" · "));
}

// -- devices --------------------------------------------------------------

function renderDevices(payload) {
  const devices = payload.devices || [];
  const limit = payload.limit;

  setText("[data-device-count]", String(devices.length));
  setText("[data-device-limit]", limit ? `/ ${limit}` : "");

  const pips = $("[data-device-pips]");
  pips.textContent = "";
  // Without a panel-side limit there is nothing to draw a bar of; the count on
  // its own is the honest answer.
  if (!limit || limit > 12) return;
  for (let i = 0; i < limit; i += 1) {
    pips.append(el("span", { "data-on": i < devices.length }));
  }
}

// -- referrals ------------------------------------------------------------

function renderReferrals(referrals, user) {
  setText("[data-referral-count]", String(referrals.referred_people ?? 0));
  const tier = referrals.tier ?? user.tier ?? 0;
  setText(
    "[data-referral-note]",
    tier >= (referrals.max_tier ?? 5)
      ? "Максимальный уровень скидки"
      : `Уровень скидки ${tier} из ${referrals.max_tier ?? 5}`
  );
}

// -- boot -----------------------------------------------------------------

boot(async (user) => {
  $("[data-copy-sub]")?.addEventListener("click", (event) => {
    const value = $("[data-sub-url]").value;
    if (value) copyText(value, event.currentTarget);
  });

  const settle = (promise, render) =>
    promise.then(render).catch((err) => {
      // One failing panel call must not blank the other three cells.
      console.error(err);
      return null;
    });

  // The subscription is the one read whose failure the visitor has to be told
  // about: every other cell is a detail, but a blank status band with no
  // explanation looks like an account that lost its subscription.
  const subscription = api("/api/subscription").catch((err) => {
    if (err instanceof ApiError && err.status === 401) throw err;
    console.error(err);
    flash("Не удалось получить состояние подписки. Обновите страницу через минуту.");
    return null;
  });

  await Promise.all([
    subscription.then((sub) => (sub ? renderSubscription(sub) : null)),
    settle(api("/api/traffic"), renderTraffic),
    settle(api("/api/devices"), renderDevices),
    settle(api("/api/referrals"), (r) => renderReferrals(r, user)),
  ]);
});
