/*
 * Devices, the subscription link, and the QR code that carries it.
 *
 * Two of the actions here are destructive in a way a customer can feel:
 * resetting the link disconnects every device at once, and removing a device
 * frees a slot someone else's phone might take. Both ask first.
 */

import { boot, hydrateIcons, clientConfig } from "./app.js";
import { toSVG } from "./qr.js";
import { PLATFORMS, guessPlatform } from "./platforms.js";
import {
  $,
  api,
  ApiError,
  copyText,
  el,
  flash,
  clearFlash,
  icon,
  show,
  withBusy,
} from "./core.js";

let subscriptionURL = "";

// -- link + QR ------------------------------------------------------------

function renderLink(url) {
  subscriptionURL = url || "";
  const has = Boolean(subscriptionURL);

  // No link means no field, no QR and no reset button: all three are actions
  // on something that does not exist yet.
  show($("[data-connect]"), has);
  show($("[data-no-connect]"), !has);
  show($("[data-qr-side]"), has);
  // Without the QR column the band is one column, not a hairline down the
  // middle of an empty half.
  $("[data-band]").dataset.single = String(!has);
  if (!has) return;

  $("[data-sub-url]").value = subscriptionURL;

  const host = $("[data-qr]");
  host.textContent = "";
  try {
    host.append(toSVG(subscriptionURL, { title: "QR-код ссылки подписки" }));
  } catch (err) {
    // A link too long for version 12 is not something the customer can fix, so
    // the copy field stays the answer rather than a broken image.
    console.error("qr", err);
    host.append(el("p", { class: "mono-sm muted", text: "QR-код не поместился — скопируйте ссылку." }));
  }
}

// -- setup instructions ---------------------------------------------------

/**
 * Turns one step's body into nodes.
 *
 * Every part goes through textContent or a real element -- the subscription
 * URL ends up inside these, and it is the one string on this page that comes
 * from outside.
 */
function renderParts(parts) {
  const nodes = [];
  for (const part of parts) {
    if (typeof part === "string") {
      nodes.push(document.createTextNode(part));
    } else if (part.code) {
      nodes.push(el("code", { class: "code", text: part.code }));
    } else if (part.open) {
      // A custom scheme: it hands over to the installed app rather than
      // navigating, so it deliberately does not open a tab.
      nodes.push(el("a", { class: "accent strong", href: part.open, text: part.text }));
    } else {
      nodes.push(
        el("a", {
          class: "accent",
          href: part.href,
          rel: "noopener",
          target: "_blank",
          text: part.text,
        })
      );
    }
  }
  return nodes;
}

function renderSteps(steps) {
  const list = el("ol", { class: "steps" });
  steps.forEach((step, index) => {
    list.append(
      el("li", { class: "step" }, [
        el("span", { class: "step-num num", text: String(index + 1).padStart(2, "0") }),
        el("div", { class: "step-body" }, [
          el("h3", { class: "mono strong", text: step.title }),
          el("p", { class: "mono-sm muted" }, renderParts(step.body)),
        ]),
      ])
    );
  });
  return list;
}

/**
 * Draws the instructions for one platform.
 *
 * Platforms whose steps embed the subscription link are not rendered without
 * one: a numbered list with an empty code block in the middle of it reads as
 * a broken page rather than as "buy a subscription first".
 */
function renderPlatform(platform) {
  const panel = $("[data-os-panel]");
  panel.textContent = "";
  panel.setAttribute("aria-label", `Инструкция: ${platform.label}`);

  if (platform.needsURL && !subscriptionURL) {
    panel.append(
      el("p", {
        class: "mono-sm muted",
        text: "Инструкция появится вместе со ссылкой подписки — оформите тариф.",
      })
    );
    return;
  }

  panel.append(renderSteps(platform.steps(subscriptionURL)));

  if (platform.fallbackNeedsURL && !subscriptionURL) return;
  panel.append(
    el("details", { class: "drop" }, [
      el("summary", { class: "mono strong", text: "Не получилось подключиться?" }),
      renderSteps(platform.fallback(subscriptionURL)),
    ])
  );
}

function selectPlatform(key) {
  const platform = PLATFORMS.find((p) => p.key === key) || PLATFORMS[0];
  for (const tab of $("[data-os-tabs]").children) {
    tab.setAttribute("aria-selected", String(tab.dataset.os === platform.key));
  }
  renderPlatform(platform);
}

function buildPlatformTabs() {
  const strip = $("[data-os-tabs]");
  if (!strip) return;
  strip.textContent = "";
  for (const platform of PLATFORMS) {
    const tab = el("button", {
      class: "chip",
      type: "button",
      role: "tab",
      "aria-selected": "false",
      "data-os": platform.key,
    });
    tab.append(icon(platform.icon), el("span", { text: platform.label }));
    tab.addEventListener("click", () => selectPlatform(platform.key));
    strip.append(tab);
  }
  selectPlatform(guessPlatform(navigator.userAgent));
}

async function resetLink(event) {
  const confirmed = confirm(
    "Сбросить ссылку подписки?\n\n" +
      "Все подключённые устройства перестанут работать, пока вы не пропишете на них новую ссылку."
  );
  if (!confirmed) return;

  await withBusy(event.currentTarget, async () => {
    clearFlash();
    try {
      const result = await api("/api/subscription/reset-link", { method: "POST" });
      renderLink(result.subscription_url);
      // The open tab still has the old link written into its steps and its
      // import button, both of which now lead nowhere.
      selectPlatform($("[data-os-tabs] [aria-selected='true']")?.dataset.os);
      flash("Ссылка обновлена. Пропишите новую на каждом устройстве.", "ok");
      await loadDevices();
    } catch (err) {
      flash(err instanceof ApiError ? err.message : "Не удалось сбросить ссылку.");
    }
  });
}

// -- device list ----------------------------------------------------------

/** Picks an icon from the platform string the panel reports. */
function deviceIcon(device) {
  const text = `${device.platform || ""} ${device.device_model || ""} ${device.os_version || ""}`.toLowerCase();
  if (/ios|iphone|ipad|android|mobile|phone/.test(text)) return "phone";
  if (/tv|appletv/.test(text)) return "tv";
  if (/mac|darwin|laptop/.test(text)) return "laptop";
  if (/win|linux|desktop/.test(text)) return "monitor";
  return "devices";
}

function deviceName(device) {
  const parts = [device.device_model, device.platform, device.os_version].filter(Boolean);
  return parts.length ? parts.join(" · ") : "Неизвестное устройство";
}

async function removeDevice(id, name, button) {
  if (!confirm(`Отключить «${name}»?\n\nСлот освободится сразу.`)) return;

  await withBusy(button, async () => {
    clearFlash();
    try {
      await api(`/api/devices/${encodeURIComponent(id)}`, { method: "DELETE" });
      flash("Устройство отключено.", "ok");
      await loadDevices();
    } catch (err) {
      flash(err instanceof ApiError ? err.message : "Не удалось отключить устройство.");
    }
  });
}

function renderDevices(payload) {
  const devices = payload.devices || [];
  const limit = payload.limit;
  const list = $("[data-device-list]");
  list.textContent = "";

  $("[data-device-summary]").textContent = limit
    ? `Занято ${devices.length} из ${limit}.`
    : `Подключено устройств: ${devices.length}.`;

  if (!devices.length) {
    list.append(
      el("li", {}, [
        icon("info", "accent"),
        el("span", {
          class: "mono-sm muted grow",
          text: "Пока ни одного. Устройство появится здесь после первого подключения.",
        }),
      ])
    );
    return;
  }

  for (const device of devices) {
    const name = deviceName(device);
    const button = el("button", {
      class: "btn btn-danger btn-sm",
      type: "button",
      "aria-label": `Отключить ${name}`,
    });
    button.append(icon("trash"));
    button.addEventListener("click", () => removeDevice(device.id, name, button));

    list.append(
      el("li", {}, [
        icon(deviceIcon(device), "accent icon-lg"),
        el("span", { class: "mono-sm strong grow", text: name }),
        button,
      ])
    );
  }
}

async function loadDevices() {
  try {
    renderDevices(await api("/api/devices"));
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) throw err;
    console.error(err);
    $("[data-device-summary]").textContent = "Не удалось получить список устройств.";
  }
}

// -- boot -----------------------------------------------------------------

boot(async () => {
  $("[data-copy-sub]")?.addEventListener("click", (event) => {
    if (subscriptionURL) copyText(subscriptionURL, event.currentTarget);
  });
  $("[data-reset]")?.addEventListener("click", resetLink);

  clientConfig().then((config) => {
    const faq = $("[data-faq]");
    if (config.faq_url && faq) {
      faq.href = config.faq_url;
      faq.hidden = false;
    }
  });

  const [subscription] = await Promise.all([api("/api/subscription"), loadDevices()]);
  renderLink(subscription.subscription_url);
  // After renderLink: the steps embed the subscription URL, so the tabs are
  // built once it is known rather than being drawn empty and filled in.
  buildPlatformTabs();
  hydrateIcons();
});
