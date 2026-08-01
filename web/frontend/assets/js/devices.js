/*
 * Devices, the subscription link, and the QR code that carries it.
 *
 * Two of the actions here are destructive in a way a customer can feel:
 * resetting the link disconnects every device at once, and removing a device
 * frees a slot someone else's phone might take. Both ask first.
 */

import { boot, hydrateIcons, clientConfig } from "./app.js";
import { toSVG } from "./qr.js";
import {
  $,
  api,
  ApiError,
  copyText,
  el,
  flash,
  clearFlash,
  icon,
  withBusy,
} from "./core.js";

let subscriptionURL = "";

// -- link + QR ------------------------------------------------------------

function renderLink(url) {
  subscriptionURL = url || "";
  $("[data-sub-url]").value = subscriptionURL;

  const host = $("[data-qr]");
  host.textContent = "";
  if (!subscriptionURL) {
    host.append(el("p", { class: "mono-sm muted", text: "Ссылка появится после активации подписки." }));
    return;
  }
  try {
    host.append(toSVG(subscriptionURL, { title: "QR-код ссылки подписки" }));
  } catch (err) {
    // A link too long for version 12 is not something the customer can fix, so
    // the copy field stays the answer rather than a broken image.
    console.error("qr", err);
    host.append(el("p", { class: "mono-sm muted", text: "QR-код не поместился — скопируйте ссылку." }));
  }
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
  hydrateIcons();
});
