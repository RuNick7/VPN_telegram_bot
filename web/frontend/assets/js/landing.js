/*
 * The landing page.
 *
 * One API call for the whole page (`/api/config`), and a background video that
 * is only ever attached when it is worth the bytes.
 */

import { $, $$, api, el, formatRub, daysLabel, plural } from "./core.js";

// -- hero video -----------------------------------------------------------

const prefersReducedMotion = () =>
  window.matchMedia("(prefers-reduced-motion: reduce)").matches;

/**
 * Whether spending ~180 KB on the moving background makes sense here.
 *
 * The poster is already in place and already looks like the design; the video
 * is decoration on top of it. Anyone who has said "not now" -- by turning on a
 * data saver, or by being on a narrow screen where the whole thing is a
 * thumbnail behind text -- gets the still.
 *
 * Reduced motion is deliberately *not* one of these. It is a separate question
 * -- "should this autoplay" rather than "is it worth fetching" -- and it is
 * answered with an offer instead of a refusal, below.
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
  const poster = $(".hero-media");
  if (!poster) return;

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
  video.addEventListener(
    "playing",
    () => {
      poster.parentElement?.remove();
    },
    { once: true }
  );
  poster.after(video);
  video.play().catch(() => video.remove());
}

/**
 * Decides between playing the background, offering it, and neither.
 *
 * Autoplaying a moving background at somebody who has asked their operating
 * system to stop animating things is the behaviour that setting exists to
 * prevent, so it is honoured. But honouring it silently means a visitor who
 * turned animations off years ago for battery reasons never learns there is
 * anything to see -- so on a screen where the video would have been worth
 * fetching anyway, it becomes a button rather than nothing.
 */
function setUpHeroBackground() {
  if (!worthFetching()) return;

  if (!prefersReducedMotion()) {
    attachHeroVideo();
    return;
  }

  const button = $("[data-play-bg]");
  if (!button) return;
  button.hidden = false;
  button.addEventListener(
    "click",
    () => {
      button.hidden = true;
      attachHeroVideo();
    },
    { once: true }
  );
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

function renderDocs(docs, supportURL) {
  let published = 0;
  for (const link of $$("[data-doc]")) {
    const url = docs?.[link.dataset.doc];
    if (!url) continue;
    link.href = url;
    link.rel = "noopener";
    link.hidden = false;
    published += 1;
  }
  const empty = $("[data-doc-empty]");
  if (empty) empty.hidden = published > 0;

  const support = $("[data-support]");
  if (support && supportURL) {
    support.href = supportURL;
    support.rel = "noopener";
    support.hidden = false;
  }
}

async function load() {
  const config = await api("/api/config");

  renderPlans(config.plans);
  renderDocs(config.docs, config.support_url);

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
