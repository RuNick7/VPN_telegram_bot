/*
 * The landing page.
 *
 * One API call for the whole page (`/api/config`): prices, the free period,
 * the referral steps, the support contact. Everything else here is
 * presentation -- the planet in the hero, the location bar under it, the
 * horizon the light page rises through, and the spotlight on the cards.
 *
 * A failed config call leaves the static copy standing: the markup already
 * carries the current prices and the support contact, so the page still says
 * what the service costs and where to ask.
 */

import { $, $$, el, formatRub, daysLabel, plural, clientConfig, trialOffer } from "./core.js";
import { Planet } from "./planet.js";
import {
  CITIES,
  HOMES,
  HOME_KEY,
  flag,
  homeByName,
  savedHome,
  zoneHome,
  locatedHome,
  estimatePing,
  quality,
} from "./places.js";

function setUpPlanet() {
  const root = $("[data-planet]");
  if (!root) return;
  const saved = savedHome();
  let origin = saved || zoneHome();
  const bar = $("[data-loc-bar]");
  const chips = new Map();

  const card = el("div", { class: "ping-card", "aria-live": "polite" }, [
    el("span", { class: "ping-place" }, [el("b"), el("span")]),
    el("span", { class: "ping-ms" }, [el("b"), el("span", { text: "пинг от вас" })]),
  ]);
  card.hidden = true;

  const showChipPing = (city) => {
    const chip = chips.get(city.id);
    if (!chip) return;
    const ms = estimatePing(origin, city);
    let tag = chip.querySelector(".chip-ms");
    if (!tag) {
      tag = el("span", { class: "chip-ms" });
      chip.append(tag);
    }
    tag.textContent = `${ms} мс`;
    tag.dataset.q = quality(ms);
  };

  const planet = new Planet(root, {
    land: "/assets/img/planet-land.png",
    origin,
    cities: CITIES,
    hero: $(".hero"),
    clearOf: $(".hero-copy"),
    avoid: [bar, $(".hero-copy")],
    onLand(city) {
      const ms = estimatePing(origin, city);
      card.querySelector(".ping-place b").replaceChildren(flag(city.id), city.city);
      card.querySelector(".ping-place span").textContent = city.country;
      card.querySelector(".ping-ms b").textContent = `≈ ${ms} мс`;
      card.dataset.q = quality(ms);
      card.hidden = false;
      card.classList.remove("is-in");
      void card.offsetWidth; // restart the entrance animation
      card.classList.add("is-in");
      showChipPing(city);
      for (const [id, chip] of chips) chip.setAttribute("aria-pressed", String(id === city.id));
      // On a phone the bar scrolls sideways: bring the city just reached into
      // view, moving only as far as it takes, so the visitor's own chip at
      // the start stays visible whenever it can.
      const active = chips.get(city.id);
      if (bar && active && bar.scrollWidth > bar.clientWidth) {
        const left = active.offsetLeft - 8;
        const right = active.offsetLeft + active.offsetWidth + 8;
        let target = bar.scrollLeft;
        if (right > bar.scrollLeft + bar.clientWidth) target = right - bar.clientWidth;
        if (left < target) target = left;
        if (target !== bar.scrollLeft) bar.scrollTo({ left: Math.max(0, target), behavior: "smooth" });
      }
    },
  });
  planet.setCard(card);

  const renderLocations = () => {
    const list = $("[data-locations]");
    if (!list) return;
    list.replaceChildren(
      ...CITIES.map((city) => {
        const ms = estimatePing(origin, city);
        return el("li", { class: "loc-row" }, [
          flag(city.id),
          el("span", { class: "loc-name" }, [el("b", { text: city.city }), el("span", { text: city.country })]),
          el("span", { class: "loc-ms", "data-q": quality(ms), text: `≈ ${ms} мс` }),
        ]);
      })
    );
    const from = $("[data-locations-from]");
    if (from) {
      const how = origin.located ? "определённого по IP" : "";
      from.textContent = `Пинг — примерный: посчитан по расстоянию от города «${origin.city}»${how ? ", " + how : ""}. Город можно сменить в полосе под планетой.`;
    }
  };

  // One place that moves the visitor: from the picker, or from the server's
  // answer about their address.
  let select = null;
  let youLabel = null;
  const applyOrigin = (next) => {
    origin = next;
    if (youLabel) youLabel.textContent = origin.label;
    if (select) {
      if (![...select.options].some((o) => o.value === origin.city)) {
        select.prepend(el("option", { value: origin.city, text: origin.city }));
      }
      select.value = origin.city;
    }
    planet.setOrigin(origin);
    for (const city of CITIES) {
      if (chips.get(city.id)?.querySelector(".chip-ms")) showChipPing(city);
    }
    renderLocations();
  };

  if (bar) {
    // The visitor's chip: their city, and a native picker laid over it.
    select = el("select", { "aria-label": "Ваш город" });
    for (const [city] of HOMES) select.append(el("option", { value: city, text: city }));
    select.value = origin.city;
    youLabel = el("span", { text: origin.label });
    const you = el("label", { class: "loc-chip loc-chip--you", title: "Выберите свой город" }, [
      el("span", { class: "you-dot" }),
      youLabel,
      chevron(),
      select,
    ]);
    select.addEventListener("change", () => {
      const picked = HOMES.some(([city]) => city === select.value) ? homeByName(select.value) : origin;
      try {
        localStorage.setItem(HOME_KEY, picked.city);
      } catch {
        // Not remembered; the choice still applies to this visit.
      }
      applyOrigin(picked);
    });
    bar.replaceChildren(you);

    CITIES.forEach((city, i) => {
      const chip = el("button", { type: "button", class: "loc-chip", "aria-pressed": "false" }, [flag(city.id), city.city]);
      chip.addEventListener("click", () => planet.jump(i));
      chips.set(city.id, chip);
      bar.append(chip);
    });
  }

  renderLocations();

  // A city the visitor chose themselves stands. Otherwise ask the server
  // where their address is; until it answers (or if it cannot), the time
  // zone's guess holds.
  if (!saved) {
    locatedHome().then((home) => {
      if (home) applyOrigin(home);
    });
  }
}

function chevron() {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", "icon");
  svg.setAttribute("viewBox", "0 0 24 24");
  svg.setAttribute("aria-hidden", "true");
  svg.innerHTML = '<path d="M6 9l6 6 6-6"/>';
  return svg;
}

// -- prices ---------------------------------------------------------------

function renderPlans(plans) {
  const host = $("[data-plans]");
  if (!host || !plans?.length) return;

  // The longest plan carries the largest saving, so it is the one worth
  // pointing at -- computed rather than hardcoded, so re-pricing cannot leave
  // the highlight on the wrong card.
  const best = plans.reduce((a, b) => (b.discount > a.discount ? b : a), plans[0]);

  host.replaceChildren(
    ...plans.map((plan) => {
      const perMonth = Math.round(plan.price / plan.months);
      return el("article", { class: "plan spot", "data-best": plan.months === best.months && best.discount > 0 }, [
        el("div", { class: "plan-top" }, [
          el("h3", { text: plan.label }),
          plan.discount > 0 ? el("span", { class: "badge", text: `−${plan.discount}%` }) : null,
        ]),
        el("div", { class: "plan-price" }, [el("b", { class: "num", text: formatRub(plan.price) })]),
        el("p", {
          class: "plan-note",
          text:
            plan.months > 1
              ? `${formatRub(perMonth)} в месяц · ${plan.days} ${plural(plan.days, "день", "дня", "дней")}`
              : `${plan.days} ${plural(plan.days, "день", "дня", "дней")} доступа`,
        }),
        el("a", { class: "btn btn-plan", href: "/login", text: "Подключить" }),
      ]);
    })
  );
}

function renderLadder(ladder) {
  const host = $("[data-referral-ladder]");
  if (!host || !Array.isArray(ladder) || ladder.length < 2) return;
  const top = ladder[0];
  host.replaceChildren(
    ...ladder.map((price, invited) =>
      el("li", { class: "step", "data-last": invited === ladder.length - 1 }, [
        el("span", { class: "step-track" }, [el("span", { class: "step-bar" })]),
        el("b", { class: "num", text: formatRub(price) }),
        el("span", { text: invited === 0 ? "без друзей" : `${invited} ${plural(invited, "друг", "друга", "друзей")}` }),
      ])
    )
  );
  // Bar heights follow the price, written through the CSSOM: the CSP forbids
  // style attributes, not style properties set from script.
  [...host.children].forEach((li, i) => {
    li.querySelector(".step-bar").style.height = `${Math.max(8, Math.round((ladder[i] / top) * 100))}%`;
  });
  host.hidden = false;
}

/**
 * The free period, from the three settings behind it: what signing up on the
 * site is worth, what signing up through the bot is worth, and what linking
 * the second identity (email onto Telegram or the other way round) adds.
 */
function renderTrial(config) {
  const offer = trialOffer(config);
  if (!offer) return;
  const { web, bot, bonus, base, most } = offer;

  let extra = "карта не нужна";
  if (bonus > 0) extra = `до ${daysLabel(most)}, если привязать почту и Telegram`;
  else if (web > bot) extra = `${daysLabel(web)} при регистрации через почту`;

  const pill = $("[data-trial-pill]");
  if (pill) {
    pill.replaceChildren(el("b", { text: `${daysLabel(base)} бесплатно` }), el("span", { text: `· ${extra}` }));
    pill.hidden = false;
  }

  const banner = $("[data-trial-banner]");
  if (!banner) return;
  $("[data-trial-base]", banner).textContent = String(base);
  $("[data-trial-base]", banner).nextElementSibling.replaceChildren(
    `${plural(base, "день", "дня", "дней")} бесплатно`,
    el("br"),
    "после регистрации"
  );
  if (bonus > 0) {
    $("[data-trial-bonus]", banner).textContent = `+${bonus}`;
    $("[data-trial-bonus-fig]", banner).hidden = false;
  }
  const lines = [];
  if (web !== bot && web > 0 && bot > 0) {
    lines.push(`Через почту — ${daysLabel(web)}, через Telegram — ${daysLabel(bot)}.`);
  }
  if (bonus > 0) {
    lines.push(`Привяжите к аккаунту и почту, и Telegram — получите ещё ${daysLabel(bonus)}, всего до ${daysLabel(most)}.`);
  }
  lines.push("Карта не нужна.");
  $("[data-trial-text]", banner).textContent = lines.join(" ");
  banner.hidden = false;
}

function renderSupport(config) {
  // footer.js points every [data-support] link at the configured address;
  // this only writes the handle out where the page shows it.
  const match = /t\.me\/([A-Za-z0-9_]+)/.exec(config.support_url || "");
  if (!match) return;
  for (const node of $$("[data-support-handle]")) node.textContent = `@${match[1]}`;
}

async function load() {
  const config = await clientConfig();
  renderPlans(config.plans);

  const cheapest = (config.plans || []).reduce(
    (min, plan) => (min === null || plan.price < min ? plan.price : min),
    null
  );
  if (cheapest !== null) {
    for (const node of $$("[data-monthly-price]")) node.textContent = formatRub(cheapest);
  }

  renderTrial(config);
  renderSupport(config);

  // Both halves of the referral sentence have to be real numbers before it is
  // worth showing, and a best price that is not actually cheaper is a claim we
  // should not make.
  const best = config.referral_best_price;
  const island = $("[data-referral]");
  if (island && best > 0 && cheapest !== null && best < cheapest) {
    for (const node of $$("[data-referral-best]")) node.textContent = formatRub(best);
    renderLadder(config.referral_ladder);
    island.hidden = false;
  }
}

// -- presentation ---------------------------------------------------------

// The light page's horizon rises with a scroll-driven CSS animation (see
// .horizon in landing.css), not from here: a scroll listener moves it a frame
// after the page has already moved, which reads as the page stuttering.

function setUpSpotlight() {
  // Cards light up under the pointer. The position goes into two custom
  // properties; the gradient itself is in the stylesheet.
  document.addEventListener("pointermove", (event) => {
    const card = event.target.closest?.(".spot");
    if (!card) return;
    const box = card.getBoundingClientRect();
    card.style.setProperty("--mx", `${event.clientX - box.left}px`);
    card.style.setProperty("--my", `${event.clientY - box.top}px`);
  });
}

function setUpHeader() {
  const header = $(".site-header");
  if (!header) return;
  // Only touch the class when it changes, so scrolling does not queue a
  // style recalculation on every event.
  let scrolled = null;
  const update = () => {
    const now = window.scrollY > 8;
    if (now === scrolled) return;
    scrolled = now;
    header.classList.toggle("is-scrolled", now);
  };
  update();
  window.addEventListener("scroll", update, { passive: true });

  // The header's blur goes on only once it is over the page below the hero
  // (see .is-past-hero): watched against the top tenth of the window, where
  // the header sits.
  const hero = $(".hero");
  if (hero) {
    new IntersectionObserver(([entry]) => header.classList.toggle("is-past-hero", !entry.isIntersecting), {
      rootMargin: "0px 0px -90% 0px",
    }).observe(hero);
  }
}

function setUpReveal() {
  const items = $$("[data-reveal]");
  if (!("IntersectionObserver" in window) || matchMedia("(prefers-reduced-motion: reduce)").matches) return;
  // The stylesheet hides sections only under this class, so a page whose
  // script never ran still shows everything.
  document.documentElement.classList.add("reveal-on");
  const seen = new IntersectionObserver(
    (entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        entry.target.classList.add("is-in");
        seen.unobserve(entry.target);
      }
    },
    { rootMargin: "0px 0px -10% 0px" }
  );
  for (const item of items) seen.observe(item);
}

setUpHeader();
setUpPlanet();
setUpSpotlight();
setUpReveal();
load().catch((err) => console.error("config", err));
