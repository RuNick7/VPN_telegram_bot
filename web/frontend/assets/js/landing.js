/*
 * The landing page.
 *
 * One API call for the whole page (`/api/config`), and a background video that
 * is only ever attached when it is worth the bytes.
 */

import { $, $$, api, el, formatRub, daysLabel, plural } from "./core.js";

// -- hero video -----------------------------------------------------------

/**
 * Whether spending ~180 KB on the moving background makes sense here.
 *
 * The poster is already in place and already looks like the design; the video
 * is decoration on top of it. Anyone who has said "not now" -- by turning on a
 * data saver, or by being on a narrow screen where the whole thing is a
 * thumbnail behind text -- gets the still.
 *
 * `prefers-reduced-motion` is deliberately not consulted. This is the site's
 * own header image and it is meant to move; the loop is slow, silent, blurred
 * and sits under a 70% scrim, which is not the kind of motion that setting
 * exists to suppress.
 */
function worthFetching() {
  if (!window.matchMedia("(min-width: 64rem)").matches) return false;

  const connection = navigator.connection;
  if (connection) {
    if (connection.saveData) return false;
    if (/(^|-)2g$/.test(connection.effectiveType || "")) return false;
  }
  return true;
}

function attachHeroVideo() {
  const hero = $(".hero");
  // The <picture> as a whole, not the <img> inside it: the poster has an AVIF
  // source alongside the fallback, and both have to go together.
  const poster = $(".hero picture") || $(".hero-media");
  if (!hero || !poster || $(".hero video")) return;

  const video = el("video", {
    class: "hero-media",
    muted: true,
    loop: true,
    playsinline: true,
    autoplay: true,
    preload: "auto",
    "aria-hidden": "true",
    tabindex: "-1",
  });
  // muted must be set as a property too, or iOS refuses to autoplay.
  video.muted = true;

  for (const [src, type] of [
    ["/assets/video/hero.av1.mp4", 'video/mp4; codecs="av01.0.05M.08"'],
    ["/assets/video/hero.webm", 'video/webm; codecs="vp9"'],
    ["/assets/video/hero.mp4", 'video/mp4; codecs="avc1.64001f"'],
  ]) {
    video.append(el("source", { src, type }));
  }

  // The poster stays in the DOM until the video actually has a frame, so a
  // failed or blocked load leaves the design intact rather than a black box.
  video.addEventListener("playing", () => poster.remove(), { once: true });

  // Appended to the hero, not next to the <img>. Inserting it after the image
  // put it *inside* the <picture>, which then took the video with it when the
  // poster was removed -- leaving an empty black hero, which is exactly what
  // it looked like.
  hero.prepend(video);
  video.play().catch(() => video.remove());
}

/** Plays the background as soon as this screen is one worth loading it on. */
function setUpHeroBackground() {
  let settled = false;

  const decide = () => {
    if (settled || !worthFetching()) return;
    settled = true;
    attachHeroVideo();
  };

  decide();

  // Re-asked when the viewport crosses the threshold, because the first answer
  // is only as good as the moment it was asked in: a window that starts narrow
  // and is dragged wider, a phone turned sideways, or a tab that was in the
  // background while the page loaded would otherwise keep the still image for
  // as long as it stays open. `settled` means this only ever adds the video,
  // never takes it away mid-visit.
  const wide = window.matchMedia("(min-width: 64rem)");
  wide.addEventListener("change", decide);
}

// -- content --------------------------------------------------------------

function renderPlans(plans) {
  const host = $("[data-plans]");
  if (!host || !plans?.length) return;

  // The longest plan carries the largest saving, so it is the one worth
  // pointing at -- computed rather than hardcoded, so re-pricing cannot leave
  // the highlight on the wrong card.
  const best = plans.reduce((a, b) => (b.discount > a.discount ? b : a), plans[0]);

  host.textContent = "";
  for (const plan of plans) {
    host.append(
      el("div", { class: "plan", "data-best": plan.months === best.months && best.discount > 0 }, [
        el("div", { class: "stack" }, [
          el("span", { class: "mono-sm muted", text: plan.label }),
          el("div", { class: "metric num", text: formatRub(plan.price) }),
          plan.discount > 0
            ? el("span", { class: "badge", text: `−${plan.discount}%` })
            : null,
        ]),
        el("span", {
          class: "mono-sm muted",
          text: `${plan.days} ${plural(plan.days, "день", "дня", "дней")} доступа`,
        }),
      ])
    );
  }
}

async function load() {
  const config = await api("/api/config");

  // The footer is not this module's business any more: every page carries the
  // same one, and assets/js/footer.js fills it on all of them.
  renderPlans(config.plans);

  const cheapest = (config.plans || []).reduce(
    (min, plan) => (min === null || plan.price < min ? plan.price : min),
    null
  );
  if (cheapest !== null) {
    for (const node of $$("[data-monthly-price]")) node.textContent = formatRub(cheapest);
  }

  // The trial is announced under the price grid rather than as a headline
  // figure: the four cells above it state what the service *is*, and those are
  // fixed facts about the infrastructure, not a promotion that can be switched
  // off in .env.
  // Said twice on purpose: next to the price, where it changes what the number
  // means, and again under the plans, where somebody is deciding.
  if (config.trial_days > 0) {
    const wording = `Первые ${daysLabel(config.trial_days)} — бесплатно, карта не нужна.`;
    for (const node of $$("[data-trial-hero], [data-trial-note]")) {
      node.textContent = wording;
      node.hidden = false;
    }
  }
}

setUpHeroBackground();
// A failed config call leaves the static copy standing: the page still says
// what the service is and still links to sign-in.
load().catch((err) => console.error("config", err));
