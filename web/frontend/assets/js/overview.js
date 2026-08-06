/*
 * Cabinet overview.
 *
 * Four independent reads (subscription, traffic, devices, referrals). They are
 * issued together and rendered as they land, because three of them go through
 * to the Remnawave panel and one slow node should not hold up the page.
 */

import { boot, clientConfig } from "./app.js";
import {
  $,
  api,
  ApiError,
  copyText,
  el,
  flash,
  formatDate,
  formatTraffic,
  plural,
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
    el("span", { class: active ? "accent" : "muted", text: active ? "Active" : "Offline" })
  );

  setText(
    "[data-status-note]",
    active
      ? "Доступ открыт. Ссылка подписки одна на все устройства."
      : "Доступ закрыт. Оформите подписку, чтобы начать пользоваться."
  );

  show($("[data-actions-active]"), active);
  show($("[data-actions-none]"), !active);

  // The plaque column exists only when there is a period to count down. The
  // band collapses to one column with it, rather than ruling a hairline down
  // the middle of an empty half.
  show($("[data-plan-side]"), active);
  $("[data-band]").dataset.single = String(!active);

  if (active) {
    // `tier` is the squad the account sits in, which is what actually decides
    // what it can reach — not what was last paid for.
    const names = { free: "Бесплатный", lte: "С квотой трафика" };
    setText("[data-plan-name]", names[sub.tier] || "Полный доступ");
    setText("[data-plan-until]", formatDate(sub.expires_at));

    // Split across two elements so the number can be set in the display size
    // and the word beside it stays small: how long is left is the question
    // this page exists to answer, and it was a line of 12px grey text.
    setText("[data-days-left]", String(sub.days_left));
    setText("[data-days-word]", plural(sub.days_left, "день", "дня", "дней"));
  }

  // The link section appears only when there is a link. An empty field that
  // takes focus when clicked reads as something that should have had a value.
  show($("[data-sub-section]"), Boolean(url));
  const field = $("[data-sub-url]");
  if (field) field.value = url;
}

// -- traffic --------------------------------------------------------------

/**
 * Matches the column count to how many cells there actually are.
 *
 * The traffic cell is two columns wide and only exists when quotas are on, so
 * without it a four-column grid drew two empty columns with a hairline
 * between them.
 */
function fitStatsGrid() {
  const grid = $("[data-stats]");
  if (!grid) return;
  // Counted, not inferred. Two of these cells come and go independently --
  // traffic with the quota feature, the Telegram one with a configured bot or
  // channel -- and a rule written for one of them drew empty columns whenever
  // the other was the one missing.
  const shown = [...grid.children].filter((cell) => !cell.hidden).length;
  for (const columns of [2, 3, 4]) {
    grid.classList.toggle(`cols-${columns}`, shown === columns);
  }
}

function renderTraffic(traffic) {
  if (!traffic?.enabled) return;

  const cell = $("[data-traffic-cell]");
  cell.hidden = false;
  setText("[data-traffic-label]", traffic.label || "Трафик");

  const total = (traffic.free_bytes || 0) + (traffic.purchased_bytes || 0);
  const remaining = Math.max(0, traffic.remaining_bytes || 0);
  const used = Math.max(0, total - remaining);

  setText("[data-traffic-used]", formatTraffic(used));
  setText("[data-traffic-total]", `/ ${formatTraffic(total)}`);

  const share = total > 0 ? Math.min(100, (used / total) * 100) : 0;
  const meter = $("[data-traffic-meter]");
  meter.dataset.low = String(total > 0 && remaining / total < 0.15);
  // Written through the CSSOM rather than as a `style` attribute in markup:
  // the former is not what `style-src` polices, so the strict CSP holds.
  meter.firstElementChild.style.width = share.toFixed(1) + "%";

  const parts = [`Осталось ${formatTraffic(remaining)}`];
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

  // From configuration rather than markup: both addresses are already in
  // .env, and a copy in the page would be a second place to forget to change.
  // One cell for both Telegram links, each shown only if configured. A card
  // naming a bot without its handle, or offering a channel we have no address
  // for, is worse than no card: the address is the only thing either is for.
  const telegramCard = clientConfig()
    .then((config) => {
      const handle = (config.telegram_bot || "").replace(/^@/, "");
      const channel = (config.channel_url || "").trim();
      if (!handle && !channel) return;

      if (handle) {
        setText("[data-bot-handle]", `@${handle}`);
        show($("[data-bot-handle]"), true);
        const link = $("[data-bot-link]");
        link.href = `https://t.me/${handle}`;
        link.hidden = false;
      } else {
        show($("[data-bot-handle]"), false);
      }

      if (channel) {
        const link = $("[data-channel-link]");
        link.href = channel;
        link.hidden = false;
      }
      $("[data-telegram-card]").hidden = false;
    })
    .catch((err) => console.error(err));

  await Promise.all([
    telegramCard,
    subscription.then((sub) => (sub ? renderSubscription(sub) : null)),
    settle(api("/api/traffic"), renderTraffic),
    settle(api("/api/devices"), renderDevices),
    settle(api("/api/referrals"), (r) => renderReferrals(r, user)),
  ]);

  // After, not inside renderTraffic: a failed traffic call leaves the cell
  // hidden too, and the grid has to fit what is on screen either way.
  fitStatsGrid();
});
