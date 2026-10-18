/*
 * The download page of «KairaVPN Проверка» (/check), where the bot's
 * «🩺 Проверить серверы» leads.
 *
 * The full list of files is in the markup, so the page works with no script;
 * this only puts the visitor's own system on the big button, or says that a
 * phone cannot run it.
 */

import { $ } from "./core.js";
import { pickFile } from "./checker.js";
import { hydrateIcons } from "./app.js";

function offer(file) {
  const button = $("[data-primary]");
  const phone = $("[data-phone]");
  if (file === "phone") {
    button.hidden = true;
    phone.hidden = false;
    return;
  }
  if (!file) return;
  button.href = file.href;
  $("[data-primary-label]").textContent = file.button;
  $("[data-primary-note]").textContent = file.system + ", " + file.detail;
}

hydrateIcons();
offer(pickFile(navigator.userAgent, "", navigator.maxTouchPoints || 0));

// Only Chromium says which processor it runs on, and only when asked.
navigator.userAgentData
  ?.getHighEntropyValues(["architecture"])
  .then(({ architecture }) => {
    if (architecture === "arm") offer(pickFile(navigator.userAgent, architecture, navigator.maxTouchPoints || 0));
  })
  .catch(() => {});
