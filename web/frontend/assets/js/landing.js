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

import { $, $$, el, formatRub, daysLabel, plural, clientConfig } from "./core.js";
import { Planet, distanceKm } from "./planet.js";

// -- locations ------------------------------------------------------------

const FLAGS = {
  fi: '<rect width="18" height="12" fill="#fff"/><rect x="5" width="3" height="12" fill="#003580"/><rect y="4.5" width="18" height="3" fill="#003580"/>',
  de: '<rect width="18" height="4" fill="#000"/><rect y="4" width="18" height="4" fill="#dd0000"/><rect y="8" width="18" height="4" fill="#ffce00"/>',
  nl: '<rect width="18" height="4" fill="#ae1c28"/><rect y="4" width="18" height="4" fill="#fff"/><rect y="8" width="18" height="4" fill="#21468b"/>',
  fr: '<rect width="6" height="12" fill="#0055a4"/><rect x="6" width="6" height="12" fill="#fff"/><rect x="12" width="6" height="12" fill="#ef4135"/>',
};

function flag(code) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", "flag");
  svg.setAttribute("viewBox", "0 0 18 12");
  svg.setAttribute("aria-hidden", "true");
  svg.innerHTML = FLAGS[code] || "";
  return svg;
}

const CITIES = [
  { id: "fi", city: "Хельсинки", country: "Финляндия", lon: 24.94, lat: 60.17 },
  { id: "de", city: "Франкфурт", country: "Германия", lon: 8.68, lat: 50.11 },
  { id: "nl", city: "Амстердам", country: "Нидерланды", lon: 4.9, lat: 52.37 },
  { id: "fr", city: "Париж", country: "Франция", lon: 2.35, lat: 48.86 },
];

// Where a visitor can say they are, for the picker on their chip and for
// naming a city the server located. Moscow and Saint Petersburg first, the
// rest alphabetical.
const HOMES = [
  ["Москва", 37.62, 55.75],
  ["Санкт-Петербург", 30.32, 59.94],
  ["Архангельск", 40.52, 64.54],
  ["Астрахань", 48.03, 46.35],
  ["Барнаул", 83.78, 53.35],
  ["Белгород", 36.58, 50.6],
  ["Брянск", 34.36, 53.24],
  ["Владивосток", 131.89, 43.12],
  ["Владимир", 40.41, 56.13],
  ["Волгоград", 44.52, 48.71],
  ["Вологда", 39.89, 59.22],
  ["Воронеж", 39.2, 51.66],
  ["Екатеринбург", 60.6, 56.84],
  ["Иваново", 40.97, 57.0],
  ["Ижевск", 53.2, 56.85],
  ["Иркутск", 104.3, 52.29],
  ["Казань", 49.11, 55.79],
  ["Калининград", 20.51, 54.71],
  ["Калуга", 36.26, 54.51],
  ["Кемерово", 86.09, 55.35],
  ["Киров", 49.67, 58.6],
  ["Краснодар", 38.98, 45.04],
  ["Красноярск", 92.87, 56.01],
  ["Курск", 36.19, 51.73],
  ["Липецк", 39.6, 52.61],
  ["Магадан", 150.8, 59.56],
  ["Махачкала", 47.5, 42.98],
  ["Мурманск", 33.08, 68.97],
  ["Набережные Челны", 52.4, 55.74],
  ["Нижний Новгород", 44.0, 56.33],
  ["Новокузнецк", 87.1, 53.76],
  ["Новосибирск", 82.92, 55.03],
  ["Омск", 73.37, 54.98],
  ["Оренбург", 55.1, 51.77],
  ["Пенза", 45.0, 53.2],
  ["Пермь", 56.25, 58.01],
  ["Петрозаводск", 34.35, 61.79],
  ["Петропавловск-Камчатский", 158.65, 53.02],
  ["Ростов-на-Дону", 39.72, 47.23],
  ["Рязань", 39.74, 54.63],
  ["Самара", 50.1, 53.2],
  ["Саратов", 46.03, 51.53],
  ["Севастополь", 33.52, 44.62],
  ["Симферополь", 34.1, 44.95],
  ["Смоленск", 32.05, 54.78],
  ["Сочи", 39.72, 43.6],
  ["Ставрополь", 41.97, 45.04],
  ["Сургут", 73.4, 61.25],
  ["Тверь", 35.9, 56.86],
  ["Тольятти", 49.42, 53.51],
  ["Томск", 84.95, 56.48],
  ["Тула", 37.62, 54.19],
  ["Тюмень", 65.53, 57.15],
  ["Улан-Удэ", 107.6, 51.83],
  ["Ульяновск", 48.4, 54.32],
  ["Уфа", 55.96, 54.74],
  ["Хабаровск", 135.07, 48.48],
  ["Чебоксары", 47.25, 56.13],
  ["Челябинск", 61.4, 55.16],
  ["Чита", 113.5, 52.03],
  ["Южно-Сахалинск", 142.73, 46.96],
  ["Якутск", 129.73, 62.03],
  ["Ярославль", 39.89, 57.63],
  ["Алматы", 76.89, 43.24],
  ["Бишкек", 74.6, 42.87],
  ["Ереван", 44.51, 40.18],
  ["Минск", 27.56, 53.9],
  ["Ташкент", 69.24, 41.31],
  ["Тбилиси", 44.8, 41.72],
];

// Time zone -> the city the guess starts from, for when the server cannot
// say (no database, or an address it does not know).
const ZONES = {
  "Europe/Moscow": "Москва",
  "Europe/Kaliningrad": "Калининград",
  "Europe/Samara": "Самара",
  "Europe/Ulyanovsk": "Ульяновск",
  "Europe/Saratov": "Саратов",
  "Europe/Astrakhan": "Астрахань",
  "Europe/Volgograd": "Волгоград",
  "Europe/Kirov": "Киров",
  "Europe/Simferopol": "Симферополь",
  "Asia/Yekaterinburg": "Екатеринбург",
  "Asia/Omsk": "Омск",
  "Asia/Novosibirsk": "Новосибирск",
  "Asia/Barnaul": "Барнаул",
  "Asia/Tomsk": "Томск",
  "Asia/Novokuznetsk": "Новокузнецк",
  "Asia/Krasnoyarsk": "Красноярск",
  "Asia/Irkutsk": "Иркутск",
  "Asia/Chita": "Чита",
  "Asia/Yakutsk": "Якутск",
  "Asia/Vladivostok": "Владивосток",
  "Asia/Khabarovsk": "Хабаровск",
  "Asia/Sakhalin": "Южно-Сахалинск",
  "Asia/Magadan": "Магадан",
  "Asia/Kamchatka": "Петропавловск-Камчатский",
  "Europe/Minsk": "Минск",
  "Asia/Almaty": "Алматы",
  "Asia/Bishkek": "Бишкек",
  "Asia/Tashkent": "Ташкент",
  "Asia/Tbilisi": "Тбилиси",
  "Asia/Yerevan": "Ереван",
};

const HOME_KEY = "kaira.home";

function homeByName(name) {
  const found = HOMES.find(([city]) => city === name) || HOMES[0];
  const [city, lon, lat] = found;
  return { city, lon, lat, label: `Вы · ${city}` };
}

/** A city the visitor picked on an earlier visit, if any. */
function savedHome() {
  try {
    const saved = localStorage.getItem(HOME_KEY);
    if (saved && HOMES.some(([city]) => city === saved)) return homeByName(saved);
  } catch {
    // No storage: nothing was saved.
  }
  return null;
}

function zoneHome() {
  let zone = "";
  try {
    zone = Intl.DateTimeFormat().resolvedOptions().timeZone;
  } catch {
    // Older engines: fall through to the default.
  }
  return homeByName(ZONES[zone] || "Москва");
}

/**
 * The server's answer for this visitor's address, named in Russian: the
 * nearest city in HOMES when it is within 60 km, which covers a suburb or a
 * district; otherwise the database's own (English) name. The coordinates are
 * always the database's, so the comet starts from the right place either way.
 */
async function locatedHome() {
  let place;
  try {
    const response = await fetch("/api/whereami", { credentials: "same-origin" });
    if (response.status !== 200) return null;
    place = await response.json();
  } catch {
    return null;
  }
  if (!Number.isFinite(place?.lat) || !Number.isFinite(place?.lon)) return null;
  let best = null;
  let bestKm = Infinity;
  for (const [city, lon, lat] of HOMES) {
    const km = distanceKm([lon, lat], [place.lon, place.lat]);
    if (km < bestKm) {
      best = city;
      bestKm = km;
    }
  }
  const city = bestKm <= 60 ? best : place.city || "ваш город";
  return { city, lon: place.lon, lat: place.lat, label: `Вы · ${city}`, located: true };
}

// A round-trip estimate from distance: light in fibre covers about 100 km of
// round trip per millisecond, real routes are longer than the great circle,
// and the last mile on either end adds its own few milliseconds.
function estimatePing(origin, city) {
  const km = distanceKm([origin.lon, origin.lat], [city.lon, city.lat]);
  return Math.round(8 + (km / 100) * 1.6);
}

// Green under 60 ms, orange above. There is deliberately no red: a slower
// server still works, and red beside a number reads as "broken".
const quality = (ms) => (ms < 60 ? "good" : "fair");

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
  const web = Number(config.trial_days) || 0;
  const bot = config.telegram_trial_days === undefined ? web : Number(config.telegram_trial_days) || 0;
  const bonus = Number(config.trial_link_bonus_days) || 0;
  const base = web > 0 && bot > 0 ? Math.min(web, bot) : Math.max(web, bot);
  if (base <= 0) return;
  const most = Math.max(web, bot) + bonus;

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
