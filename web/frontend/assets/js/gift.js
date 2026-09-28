/*
 * Redeeming a gift link.
 *
 * The code is in the path (`/gift/CODE`), which is what makes a gift usable by
 * someone who has never opened Telegram — the bot's promo code and this link
 * are two doors onto the same single-use code, so redeeming either closes both.
 *
 * Redemption itself needs an account, because a gift is days added to a
 * subscription and there is nothing to add them to otherwise. So a signed-out
 * visitor is sent to sign in with the code carried along, not turned away.
 */

import {
  $,
  api,
  ApiError,
  daysLabel,
  flash,
  clearFlash,
  formatDate,
  promoCodeFrom,
  withBusy,
} from "./core.js";
import { hydrateIcons } from "./app.js";

const code = promoCodeFrom(location.pathname);

function setStage(name) {
  for (const stage of ["need-login", "can-redeem", "done"]) {
    const node = $(`[data-${stage}]`);
    if (node) node.hidden = stage !== name;
  }
}

async function redeem(event) {
  await withBusy(event.currentTarget, async () => {
    clearFlash();
    try {
      const result = await api("/api/promo/redeem", { method: "POST", body: { code } });
      $("[data-title]").textContent = "Подарок активирован";
      $("[data-subtitle]").textContent =
        `${daysLabel(result.days_added)} добавлено. Подписка активна до ${formatDate(result.expires_at)}.`;
      setStage("done");
      flash("Готово. Ссылку для подключения найдёте в кабинете.", "ok");
    } catch (err) {
      if (err instanceof ApiError && err.status === 401) {
        setStage("need-login");
        flash("Сессия истекла — войдите ещё раз, код не потрачен.");
        return;
      }
      // A spent or invalid code is the customer's answer, not a retry: the
      // button goes away so nobody hammers it.
      setStage("done");
      $("[data-title]").textContent = "Код не подошёл";
      $("[data-subtitle]").textContent = "";
      flash(err instanceof ApiError ? err.message : "Не удалось активировать подарок.");
    }
  });
}

async function start() {
  hydrateIcons();

  if (!code) {
    $("[data-code]").textContent = "—";
    $("[data-title]").textContent = "Ссылка неполная";
    $("[data-subtitle]").textContent =
      "В адресе нет кода подарка. Проверьте, что ссылка скопирована целиком.";
    return;
  }

  $("[data-code]").textContent = code;
  $("[data-login-link]").href = "/login?next=" + encodeURIComponent(location.pathname);

  try {
    await api("/api/me");
    setStage("can-redeem");
    $("[data-redeem]").addEventListener("click", redeem);
  } catch (err) {
    if (err instanceof ApiError && err.status === 401) {
      setStage("need-login");
      return;
    }
    // Offline or a server fault: offer the sign-in route rather than a button
    // that would fail for a reason the visitor cannot act on.
    setStage("need-login");
    flash(err instanceof ApiError ? err.message : "Нет связи с сервером.");
  }
}

start();
