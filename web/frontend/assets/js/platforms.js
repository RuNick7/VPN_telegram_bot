/*
 * Per-device setup instructions, mirroring the bot's PLATFORMS table.
 *
 * The bot has had step-by-step instructions per operating system since the
 * beginning (user_bot/handlers/setup.py); the site had a grid of download
 * links and nothing else. Same seven platforms, same order, same steps.
 *
 * Pure data. Nothing here touches the DOM, so the whole table can be checked
 * from `node --test` -- and it is, because an instruction that is subtly wrong
 * looks exactly like one that is right.
 *
 * A step's body is a list of parts:
 *   "text"                  -- plain text
 *   {href, text}            -- a link out
 *   {open, text}            -- a link that hands over to the installed app
 *   {code}                  -- a block of text meant to be copied
 */

/** The app's own import scheme. One tap in the app rather than a paste. */
export function importLink(subscriptionURL) {
  return "happ://add/" + subscriptionURL;
}

const HAPP_ANDROID = "https://play.google.com/store/apps/details?id=com.happproxy&hl=ru";
const HAPP_APPLE = "https://apps.apple.com/us/app/happ-proxy-utility/id6504287215";
const HAPP_APPLE_RU = "https://apps.apple.com/ru/app/happ-proxy-utility-plus/id6746188973";
const HAPP_WINDOWS =
  "https://github.com/Happ-proxy/happ-desktop/releases/latest/download/setup-Happ.x64.exe";
const HAPP_APK =
  "https://github.com/Happ-proxy/happ-android/releases/latest/download/Happ.apk";
const HAPP_APPLE_TV = "https://apps.apple.com/us/app/happ-proxy-utility-for-tv/id6748297274";
const NEKORAY_ZIP =
  "https://github.com/MatsuriDayo/nekoray/releases/download/4.0.1/nekoray-4.0.1-2024-12-12-linux64.zip";
const NEKORAY_DEB =
  "https://github.com/MatsuriDayo/nekoray/releases/download/4.0.1/nekoray-4.0.1-2024-12-12-debian-x64.deb";

const APPLE_INSTALL = [
  "Установите ",
  { href: HAPP_APPLE, text: "Happ" },
  " из App Store. Для российского аккаунта — ",
  { href: HAPP_APPLE_RU, text: "Happ (RU)" },
  ".",
];

/**
 * The flow four platforms share: install, tap to import, connect.
 *
 * Only the first step differs between Android, iOS, Windows and macOS, so it
 * is the only thing each of them supplies -- the same reason the bot builds
 * these with one function.
 */
function happFlow(install) {
  return (url) => [
    { title: "Установите приложение", body: install },
    {
      title: "Импортируйте профиль",
      body: [
        "Нажмите ",
        { open: importLink(url), text: "эту ссылку" },
        " — Happ откроется и подхватит конфигурацию сам. Если ничего не произошло, скопируйте ссылку подписки выше и добавьте её вручную через ",
        "+",
        " → «Из буфера обмена».",
      ],
    },
    {
      title: "Включите VPN",
      body: ["Откройте Happ, выберите сервер и нажмите кнопку подключения."],
    },
  ];
}

/** The "it did not work" fallback every Happ platform shares. */
function clipboardFallback(url) {
  return [
    { title: "Скопируйте ссылку подписки", body: [{ code: url }] },
    { title: "Откройте Happ", body: ["Нажмите ", "+", " в правом верхнем углу."] },
    {
      title: "Импортируйте из буфера обмена",
      body: ["Выберите сервер и нажмите кнопку подключения."],
    },
  ];
}

const TV_PAIRING = [
  {
    title: "Настройте телефон",
    body: [
      "Установите Happ на телефон и подключите VPN по инструкции из вкладки Android или iPhone.",
    ],
  },
  {
    title: "Отсканируйте QR-код с телевизора",
    body: [
      "В приложении на телефоне выберите отправку конфигураций — они уйдут на телевизор.",
    ],
  },
  {
    title: "Включите VPN",
    body: ["Выберите конфигурацию на телевизоре и нажмите кнопку подключения."],
  },
];

export const PLATFORMS = [
  {
    key: "android",
    label: "Android",
    icon: "phone",
    needsURL: true,
    steps: happFlow([
      "Установите ",
      { href: HAPP_ANDROID, text: "Happ" },
      " из Google Play.",
    ]),
    fallback: clipboardFallback,
    fallbackNeedsURL: true,
  },
  {
    key: "ios",
    label: "iPhone / iPad",
    icon: "phone",
    needsURL: true,
    steps: happFlow(APPLE_INSTALL),
    fallback: clipboardFallback,
    fallbackNeedsURL: true,
  },
  {
    key: "windows",
    label: "Windows",
    icon: "monitor",
    needsURL: true,
    steps: happFlow([
      "Скачайте ",
      { href: HAPP_WINDOWS, text: "Happ для Windows" },
      " и установите его.",
    ]),
    fallback: clipboardFallback,
    fallbackNeedsURL: true,
  },
  {
    key: "macos",
    label: "macOS",
    icon: "laptop",
    needsURL: true,
    steps: happFlow(APPLE_INSTALL),
    fallback: clipboardFallback,
    fallbackNeedsURL: true,
  },
  {
    key: "linux",
    label: "Linux",
    icon: "monitor",
    needsURL: true,
    steps: (url) => [
      {
        title: "Скачайте NekoRay",
        body: [
          { href: NEKORAY_ZIP, text: "ZIP для Linux" },
          " или ",
          { href: NEKORAY_DEB, text: "DEB для Debian/Ubuntu" },
          ".",
        ],
      },
      {
        title: "Распакуйте и запустите",
        body: [
          "Распакуйте архив в любую папку и запустите launcher или nekobox. Если ставили DEB — запустите из меню приложений.",
        ],
      },
      { title: "Скопируйте ссылку подписки", body: [{ code: url }] },
      {
        title: "Добавьте профиль",
        body: [
          "Сервер → Добавить профиль из буфера обмена → «Как подписку (создать новую группу)». Откройте появившуюся вкладку.",
        ],
      },
      {
        title: "Включите режим TUN",
        body: [
          "Переключатель вверху экрана. Он пускает через VPN весь трафик системы; если нужен только браузер — выберите «Системный прокси». NekoRay может попросить перезапуск.",
        ],
      },
      {
        title: "Проверьте и запустите",
        body: [
          "Нажмите «URL-Тест», затем правой кнопкой по конфигурации → «Запустить». Остановить — там же.",
        ],
      },
      {
        title: "Обновление подписки",
        body: ["Сервер → Текущая группа → Обновить подписки."],
      },
    ],
    fallback: () => [
      {
        title: "Напишите в поддержку",
        body: [
          "На Linux конфигурации у клиентов расходятся сильнее всего. Опишите дистрибутив и что именно не выходит — разберём.",
        ],
      },
    ],
    fallbackNeedsURL: false,
  },
  {
    key: "tv",
    label: "Android TV",
    icon: "tv",
    needsURL: false,
    steps: () => [
      {
        title: "Установите Happ на телевизор",
        body: [
          { href: HAPP_ANDROID, text: "Google Play" },
          " или ",
          { href: HAPP_APK, text: "APK-файл" },
          ". APK можно скачать на флешку, вставить её в телевизор и открыть файл через файловый менеджер.",
        ],
      },
      ...TV_PAIRING,
    ],
    fallback: () => [
      {
        title: "Скачайте QR-код на флешку",
        body: ["Сохраните изображение QR-кода с этой страницы и вставьте флешку в телевизор."],
      },
      {
        title: "Добавьте профиль с флешки",
        body: ["В Happ на телевизоре: ", "+", " → добавление через QR-код → укажите файл на флешке."],
      },
    ],
    fallbackNeedsURL: false,
  },
  {
    key: "appletv",
    label: "Apple TV",
    icon: "tv",
    needsURL: false,
    steps: () => [
      {
        title: "Установите Happ на Apple TV",
        body: [{ href: HAPP_APPLE_TV, text: "Happ для Apple TV" }, " из App Store."],
      },
      ...TV_PAIRING,
    ],
    fallback: () => [
      {
        title: "Выберите «Web Import»",
        body: ["На экране импорта в приложении на телевизоре."],
      },
      {
        title: "Откройте tv.happ.su",
        body: [
          "В любом браузере введите временный код с экрана телевизора, добавьте данные и нажмите «Отправить».",
        ],
      },
    ],
    fallbackNeedsURL: false,
  },
];

/**
 * Which tab to open on arrival.
 *
 * A guess from the user agent, and only a guess: it decides which of seven
 * tabs is preselected, nothing else. Everything stays one click away if it
 * picks wrong.
 */
export function guessPlatform(userAgent = "") {
  const ua = userAgent.toLowerCase();
  if (/iphone|ipad|ipod/.test(ua)) return "ios";
  if (/android/.test(ua)) return "android";
  if (/windows/.test(ua)) return "windows";
  if (/mac os x|macintosh/.test(ua)) return "macos";
  if (/linux|x11|cros/.test(ua)) return "linux";
  return "windows";
}
