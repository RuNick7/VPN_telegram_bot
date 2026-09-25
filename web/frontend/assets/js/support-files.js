/*
 * What the support page lets a customer attach, checked before anything is
 * sent.
 *
 * The server checks all of this again, and more thoroughly -- it reads the
 * bytes, not the name. This copy exists so a 60 MB video is refused in the
 * second it takes to pick it, rather than after two minutes of uploading on a
 * phone. The numbers match web/internal/support/support.go.
 */

const MB = 1024 * 1024;

export const LIMITS = {
  files: 3,
  image: 10 * MB,
  video: 45 * MB,
  document: 10 * MB,
  total: 50 * MB,
};

const KIND_BY_TYPE = {
  "image/jpeg": "image",
  "image/png": "image",
  "image/webp": "image",
  "video/mp4": "video",
  "video/quicktime": "video",
  "video/webm": "video",
  "application/pdf": "document",
  "text/plain": "document",
};

// Some browsers report no type at all for a file they do not recognise --
// `.log` most often -- so the name is the fallback.
const KIND_BY_EXTENSION = {
  jpg: "image",
  jpeg: "image",
  png: "image",
  webp: "image",
  mp4: "video",
  m4v: "video",
  mov: "video",
  webm: "video",
  pdf: "document",
  txt: "document",
  log: "document",
};

/** The `accept` attribute for the file inputs. */
export const ACCEPT = [
  ...Object.keys(KIND_BY_TYPE),
  ...Object.keys(KIND_BY_EXTENSION).map((ext) => "." + ext),
].join(",");

export const ACCEPTED_HINT =
  "Можно приложить фото (JPG, PNG, WebP), видео (MP4, MOV, WebM), PDF или текстовый файл.";

/** "image", "video", "document", or "" for something not accepted. */
export function kindOf(file) {
  const byType = KIND_BY_TYPE[file.type];
  if (byType) return byType;
  const ext = String(file.name || "").split(".").pop().toLowerCase();
  // A browser that did name a type gets believed about what it is *not*: an
  // HEIC photo renamed to .jpg is still refused here.
  if (file.type && !file.type.startsWith("text/")) return "";
  return KIND_BY_EXTENSION[ext] || "";
}

/**
 * The first problem with a selection, worded for the customer, or null.
 *
 * One message at a time on purpose: it goes into a single notice, and the
 * fix for the first is often the fix for the rest.
 */
export function checkFiles(files) {
  const list = [...files];
  if (list.length > LIMITS.files) {
    return `Можно приложить не больше ${LIMITS.files} файлов.`;
  }
  let total = 0;
  for (const file of list) {
    const kind = kindOf(file);
    if (!kind) return `Файл «${file.name}» не подходит. ${ACCEPTED_HINT}`;
    if (file.size === 0) return `Файл «${file.name}» пустой.`;
    const limit = LIMITS[kind];
    if (file.size > limit) return `Файл «${file.name}» больше ${limit / MB} МБ.`;
    total += file.size;
  }
  if (total > LIMITS.total) {
    return `Все файлы вместе — не больше ${LIMITS.total / MB} МБ.`;
  }
  return null;
}

/** "340 КБ", "12,5 МБ" -- a file's size the way its owner thinks of it. */
export function formatSize(bytes) {
  const value = Number(bytes) || 0;
  if (value < MB) return `${Math.max(1, Math.round(value / 1024))} КБ`;
  const mb = value / MB;
  return `${mb >= 10 ? Math.round(mb) : mb.toFixed(1).replace(".0", "").replace(".", ",")} МБ`;
}

/** How a ticket's state reads to the customer, and the badge colour for it. */
export function statusView(status) {
  switch (status) {
    case "answered":
      return { label: "Есть ответ", kind: "" };
    case "closed":
      return { label: "Закрыто", kind: "off" };
    default:
      return { label: "На рассмотрении", kind: "on" };
  }
}

/** The ticket named in `?id=`, or null. */
export function ticketFromSearch(search) {
  const raw = new URLSearchParams(search).get("id");
  return raw && /^[1-9][0-9]{0,17}$/.test(raw) ? raw : null;
}
