/*
 * Per-device setup instructions, mirroring the bot's PLATFORMS table.
 *
 * The bot has had step-by-step instructions per operating system since the
 * beginning (user_bot/handlers/setup.py); the site had a grid of download
 * links and nothing else. Same seven platforms, same order, same steps.
 *
 * Every platform uses one app, Incy: it takes the full Xray JSON the panel
 * serves, balancers included, on phones, desktops and TVs alike. Happ is gone
 * from both the bot and the site.
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
  return "incy://import/" + subscriptionURL;
}

// The real Incy is published by LLC ITDEV. It is not in the Russian App Store,
// and the Russian store carries look-alikes under the same name from other
// sellers -- which is why the publisher is named wherever the link is.
const INCY_APPLE = "https://apps.apple.com/us/app/incy/id6756943388";
const INCY_ANDROID = "https://play.google.com/store/apps/details?id=llc.itdev.incy";
// The project keeps a release under the fixed tag `latest` and re-uploads its
// files there on every build, so these names never go stale. Not
// /releases/latest/download/: the newest release is often an Android-only one
// with no desktop files in it.
const INCY_RELEASES = "https://github.com/INCY-DEV/incy-platforms/releases/tag/latest";
const INCY_DOWNLOAD = "https://github.com/INCY-DEV/incy-platforms/releases/download/latest/";
const INCY_APK = INCY_DOWNLOAD + "Incy.apk";
const INCY_WINDOWS = INCY_DOWNLOAD + "incy-windows-setup.exe";
const INCY_WINDOWS_PORTABLE = INCY_DOWNLOAD + "incy-windows-portable.zip";
const INCY_MAC_ARM = INCY_DOWNLOAD + "incy-macos-arm64.dmg";
const INCY_MAC_INTEL = INCY_DOWNLOAD + "incy-macos-intel.dmg";
const INCY_LINUX_DEB = INCY_DOWNLOAD + "incy-linux-x64.deb";
const INCY_LINUX_RPM = INCY_DOWNLOAD + "incy-linux-x64.rpm";
const INCY_LINUX_ARCH = INCY_DOWNLOAD + "incy-linux-x64.pkg.tar.zst";
const INCY_LINUX_ARM_DEB = INCY_DOWNLOAD + "incy-linux-arm64.deb";
const INCY_LINUX_ARM_RPM = INCY_DOWNLOAD + "incy-linux-arm64.rpm";
const APPLE_ACCOUNT = "https://account.apple.com/";

/**
 * The flow phones and desktops share: install, tap to import, connect.
 *
 * Only the first step differs between them, so it is the only thing each one
 * supplies -- the same reason the bot builds these with one function.
 */
function incyFlow(install) {
  return (url) => [
    { title: "Установите Incy", body: install },
    {
      title: "Добавьте подписку",
      body: [
        "Нажмите ",
        { open: importLink(url), text: "эту ссылку" },
        " — Incy откроется и добавит подписку сам. Если ничего не произошло, скопируйте ссылку подписки выше и добавьте её в Incy вручную, из буфера обмена.",
      ],
    },
    {
      title: "Включите VPN",
      body: ["Откройте Incy, выберите сервер и нажмите кнопку подключения."],
    },
  ];
}

/** The "it did not work" fallback every phone and desktop shares. */
function clipboardFallback(url) {
  return [
    { title: "Скопируйте ссылку подписки", body: [{ code: url }] },
    {
      title: "Добавьте подписку в Incy",
      body: ["Откройте Incy и добавьте подписку из буфера обмена."],
    },
    { title: "Включите VPN", body: ["Выберите сервер и нажмите кнопку подключения."] },
  ];
}

/**
 * How to get Incy when the App Store does not show it.
 *
 * The app is missing from the Russian store, so anyone signed in with a
 * Russian Apple ID searches, finds nothing (or a fake) and gives up. Two ways
 * round it, the gentler first: a separate Apple ID touches nothing but the
 * App Store, while changing the country of the main one has preconditions
 * Apple enforces.
 */
export const APP_STORE_REGION = {
  title: "Не находите Incy в App Store?",
  steps: () => [
    {
      title: "Почему его нет",
      body: [
        "В российском App Store Incy нет, а приложения с похожим названием — подделки. Настоящий Incy выпускает LLC ITDEV. Чтобы его скачать, нужен Apple ID другой страны, например США. Это можно сделать одним из двух способов ниже.",
      ],
    },
    {
      title: "Способ 1: отдельный Apple ID для App Store",
      body: [
        "Создайте новый Apple ID на ",
        { href: APPLE_ACCOUNT, text: "account.apple.com" },
        " и укажите страну США. В App Store нажмите на аватар → «Выйти» и войдите с новым Apple ID — только в App Store, не в настройках iCloud. Фото, контакты и iCloud остаются на основном аккаунте.",
      ],
    },
    {
      title: "Способ 2: сменить страну основного Apple ID",
      body: [
        "Настройки → ваше имя → «Медиаматериалы и покупки» → «Просмотреть» → «Страна или регион» → «Изменить страну или регион». Выберите США, примите условия, способ оплаты — «Нет», адрес — любой адрес в США. Перед этим отмените активные подписки и потратьте остаток на балансе Apple ID: иначе Apple не даст сменить страну.",
      ],
    },
    {
      title: "Установите Incy",
      body: [
        "Откройте ",
        { href: INCY_APPLE, text: "Incy в App Store" },
        " (разработчик LLC ITDEV) и установите. После этого можно вернуться к прежнему Apple ID — Incy останется и будет работать, а обновлять его нужно будет из того аккаунта, с которого он установлен.",
      ],
    },
  ],
};

const TV_PAIRING = [
  {
    title: "Настройте телефон",
    body: [
      "Установите Incy на телефон и добавьте подписку по инструкции из вкладки Android или iPhone.",
    ],
  },
  {
    title: "Передайте подписку на телевизор",
    body: [
      "Откройте Incy на телевизоре и перейдите к добавлению подписки — на экране появятся код из 8 символов и QR-код. В Incy на телефоне отсканируйте QR-код или введите код: подписка перейдёт на телевизор.",
    ],
  },
  {
    title: "Включите VPN",
    body: ["Выберите сервер на телевизоре и нажмите кнопку подключения."],
  },
];

const TV_FALLBACK = [
  {
    title: "Код устарел",
    body: [
      "Код действует 5 минут. Закройте экран добавления подписки на телевизоре и откройте снова — появится новый.",
    ],
  },
  {
    title: "Подписка не пришла",
    body: [
      "Проверьте, что на телефоне подписка уже добавлена и VPN подключается. Удобнее всего, когда телефон и телевизор в одной сети Wi-Fi, но передача работает и через интернет.",
    ],
  },
];

export const PLATFORMS = [
  {
    key: "android",
    label: "Android",
    icon: "phone",
    needsURL: true,
    steps: incyFlow([
      "Установите ",
      { href: INCY_ANDROID, text: "Incy" },
      " из Google Play. Если Google Play недоступен — скачайте ",
      { href: INCY_APK, text: "APK-файл" },
      ".",
    ]),
    fallback: clipboardFallback,
    fallbackNeedsURL: true,
  },
  {
    key: "ios",
    label: "iPhone / iPad",
    icon: "phone",
    needsURL: true,
    steps: incyFlow([
      "Установите ",
      { href: INCY_APPLE, text: "Incy" },
      " из App Store — разработчик LLC ITDEV. Если в App Store его не видно, ниже написано, что делать.",
    ]),
    fallback: clipboardFallback,
    fallbackNeedsURL: true,
    extra: APP_STORE_REGION,
  },
  {
    key: "windows",
    label: "Windows",
    icon: "monitor",
    needsURL: true,
    steps: incyFlow([
      "Скачайте ",
      { href: INCY_WINDOWS, text: "установщик Incy для Windows" },
      " и запустите его. Без установки — ",
      { href: INCY_WINDOWS_PORTABLE, text: "portable-версия" },
      ".",
    ]),
    fallback: clipboardFallback,
    fallbackNeedsURL: true,
  },
  {
    key: "macos",
    label: "macOS",
    icon: "laptop",
    needsURL: true,
    // The .dmg rather than the App Store: it needs no change of App Store
    // region, and it is the only build for Intel Macs at all.
    steps: incyFlow([
      "Скачайте Incy для своего Mac: ",
      { href: INCY_MAC_ARM, text: "Apple Silicon (M1 и новее)" },
      " или ",
      { href: INCY_MAC_INTEL, text: "Intel" },
      ". Откройте файл .dmg и перетащите Incy в «Программы».",
    ]),
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
        title: "Скачайте Incy",
        body: [
          { href: INCY_LINUX_DEB, text: "DEB для Debian и Ubuntu" },
          ", ",
          { href: INCY_LINUX_RPM, text: "RPM для Fedora" },
          " или ",
          { href: INCY_LINUX_ARCH, text: "пакет для Arch" },
          ". Для ARM64: ",
          { href: INCY_LINUX_ARM_DEB, text: "DEB" },
          " или ",
          { href: INCY_LINUX_ARM_RPM, text: "RPM" },
          ". Остальные сборки — на ",
          { href: INCY_RELEASES, text: "странице релиза" },
          ".",
        ],
      },
      {
        title: "Установите и запустите",
        body: [
          "Из папки, куда скачался пакет, — одной из команд:",
          { code: "sudo apt install ./incy-linux-x64.deb" },
          { code: "sudo dnf install ./incy-linux-x64.rpm" },
          { code: "sudo pacman -U incy-linux-x64.pkg.tar.zst" },
          "Затем запустите Incy из меню приложений.",
        ],
      },
      {
        title: "Добавьте подписку",
        body: [
          "Нажмите ",
          { open: importLink(url), text: "эту ссылку" },
          " — Incy откроется и добавит подписку сам. Если ничего не произошло, скопируйте ссылку и добавьте её в Incy из буфера обмена:",
          { code: url },
        ],
      },
      {
        title: "Включите VPN",
        body: ["Выберите сервер и нажмите кнопку подключения."],
      },
    ],
    fallback: () => [
      {
        title: "Напишите в поддержку",
        body: [
          "На Linux системы у клиентов расходятся сильнее всего. Опишите дистрибутив и что именно не выходит — разберём.",
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
        title: "Установите Incy на телевизор",
        body: [
          { href: INCY_ANDROID, text: "Google Play" },
          " или ",
          { href: INCY_APK, text: "APK-файл" },
          ". APK можно скачать на флешку, вставить её в телевизор и открыть файл через файловый менеджер.",
        ],
      },
      ...TV_PAIRING,
    ],
    fallback: () => TV_FALLBACK,
    fallbackNeedsURL: false,
  },
  {
    key: "appletv",
    label: "Apple TV",
    icon: "tv",
    needsURL: false,
    steps: () => [
      {
        title: "Установите Incy на Apple TV",
        body: [
          { href: INCY_APPLE, text: "Incy" },
          " из App Store на телевизоре (разработчик LLC ITDEV, нужен tvOS 17 или новее).",
        ],
      },
      ...TV_PAIRING,
    ],
    fallback: () => TV_FALLBACK,
    fallbackNeedsURL: false,
    extra: APP_STORE_REGION,
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
