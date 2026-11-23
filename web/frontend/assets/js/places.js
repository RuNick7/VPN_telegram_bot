/*
 * Places: where the servers are, where the visitor probably is, and how far
 * apart they are. Shared by the landing page's planet and the cabinet's globe,
 * so both name the same cities and quote the same ping for the same visitor.
 */

const DEG = Math.PI / 180;

/** Great-circle distance in kilometres between two [lon, lat] points. */
export function distanceKm([lon1, lat1], [lon2, lat2]) {
  const c =
    Math.sin(lat1 * DEG) * Math.sin(lat2 * DEG) +
    Math.cos(lat1 * DEG) * Math.cos(lat2 * DEG) * Math.cos((lon1 - lon2) * DEG);
  return Math.acos(Math.max(-1, Math.min(1, c))) * 6371;
}

export const FLAGS = {
  fi: '<rect width="18" height="12" fill="#fff"/><rect x="5" width="3" height="12" fill="#003580"/><rect y="4.5" width="18" height="3" fill="#003580"/>',
  de: '<rect width="18" height="4" fill="#000"/><rect y="4" width="18" height="4" fill="#dd0000"/><rect y="8" width="18" height="4" fill="#ffce00"/>',
  nl: '<rect width="18" height="4" fill="#ae1c28"/><rect y="4" width="18" height="4" fill="#fff"/><rect y="8" width="18" height="4" fill="#21468b"/>',
  fr: '<rect width="6" height="12" fill="#0055a4"/><rect x="6" width="6" height="12" fill="#fff"/><rect x="12" width="6" height="12" fill="#ef4135"/>',
};

export function flag(code) {
  const svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
  svg.setAttribute("class", "flag");
  svg.setAttribute("viewBox", "0 0 18 12");
  svg.setAttribute("aria-hidden", "true");
  svg.innerHTML = FLAGS[code] || "";
  return svg;
}

export const CITIES = [
  { id: "fi", city: "Хельсинки", country: "Финляндия", lon: 24.94, lat: 60.17 },
  { id: "de", city: "Франкфурт", country: "Германия", lon: 8.68, lat: 50.11 },
  { id: "nl", city: "Амстердам", country: "Нидерланды", lon: 4.9, lat: 52.37 },
  { id: "fr", city: "Париж", country: "Франция", lon: 2.35, lat: 48.86 },
];

// Where a visitor can say they are, for the picker on their chip and for
// naming a city the server located. Moscow and Saint Petersburg first, the
// rest alphabetical.
export const HOMES = [
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
export const ZONES = {
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

export const HOME_KEY = "kaira.home";

export function homeByName(name) {
  const found = HOMES.find(([city]) => city === name) || HOMES[0];
  const [city, lon, lat] = found;
  return { city, lon, lat, label: `Вы · ${city}` };
}

/** A city the visitor picked on an earlier visit, if any. */
export function savedHome() {
  try {
    const saved = localStorage.getItem(HOME_KEY);
    if (saved && HOMES.some(([city]) => city === saved)) return homeByName(saved);
  } catch {
    // No storage: nothing was saved.
  }
  return null;
}

export function zoneHome() {
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
export async function locatedHome() {
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
export function estimatePing(origin, city) {
  const km = distanceKm([origin.lon, origin.lat], [city.lon, city.lat]);
  return Math.round(8 + (km / 100) * 1.6);
}

// Green under 60 ms, orange above. There is deliberately no red: a slower
// server still works, and red beside a number reads as "broken".
export const quality = (ms) => (ms < 60 ? "good" : "fair");

