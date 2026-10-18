/*
 * The files of «KairaVPN Проверка», the program that checks a customer's
 * servers and sends the report into their support ticket.
 *
 * They are built and published by the program's own public repository,
 * github.com/RuNick7/vpn-check; /releases/latest/download/ always resolves to
 * the newest release, and the files carry no version in their names, so these
 * links never go stale. jstest pins the names against vpncheck/build.sh.
 *
 * Pure data and one guess, so both are checked from `node --test`.
 */

export const RELEASES = "https://github.com/RuNick7/vpn-check/releases/latest";

const download = (name) => RELEASES + "/download/" + name;

export const FILES = [
  {
    key: "macos",
    system: "macOS 12 и новее",
    detail: "Apple M1–M4 и Intel",
    name: "KairaVPN-Check.dmg",
    button: "Скачать для macOS",
  },
  {
    key: "windows-x64",
    system: "Windows 10 и 11",
    detail: "обычные компьютеры (x64)",
    name: "KairaVPN-Check-x64.exe",
    button: "Скачать для Windows",
  },
  {
    key: "windows-arm64",
    system: "Windows 11 на ARM",
    detail: "Snapdragon и другие ARM",
    name: "KairaVPN-Check-arm64.exe",
    button: "Скачать для Windows на ARM",
  },
  {
    key: "linux-x64",
    system: "Linux с рабочим столом",
    detail: "x64, откроется в браузере",
    name: "KairaVPN-Check-linux-x64",
    button: "Скачать для Linux",
  },
  {
    key: "linux-arm64",
    system: "Linux с рабочим столом",
    detail: "ARM64, откроется в браузере",
    name: "KairaVPN-Check-linux-arm64",
    button: "Скачать для Linux (ARM64)",
  },
].map((file) => ({ ...file, href: download(file.name) }));

/**
 * The file to offer first, from the user agent and, where the browser tells
 * them, the processor (Chromium's userAgentData) and touch points.
 *
 * "phone" when the visitor is on a phone or tablet: the program is for
 * computers, and they should be told so rather than handed an .exe. null when
 * nothing fits; the full list is on the page either way.
 */
export function pickFile(userAgent = "", architecture = "", touchPoints = 0) {
  const ua = userAgent.toLowerCase();
  const arm = architecture === "arm" || /aarch64|arm64/.test(ua);
  const key = (k) => FILES.find((file) => file.key === k);
  if (/iphone|ipad|ipod|android/.test(ua)) return "phone";
  // Windows on ARM reports itself as x64 in the user agent; only
  // userAgentData knows better. The x64 file runs there too, emulated.
  if (/windows/.test(ua)) return key(arm ? "windows-arm64" : "windows-x64");
  // An iPad asks for the desktop site and says it is a Mac; a Mac has no
  // touch screen.
  if (/mac os x|macintosh/.test(ua)) return touchPoints > 1 ? "phone" : key("macos");
  if (/cros/.test(ua)) return null;
  if (/linux|x11/.test(ua)) return key(arm ? "linux-arm64" : "linux-x64");
  return null;
}
