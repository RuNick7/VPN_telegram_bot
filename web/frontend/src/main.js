const output = document.getElementById("output");
const telegramLoginButton = document.getElementById("telegram-login-btn");
const telegramWidgetContainer = document.getElementById("telegram-widget-container");
const requestMagicLinkButton = document.getElementById("magic-request-btn");
const verifyMagicLinkButton = document.getElementById("magic-verify-btn");
const emailInput = document.getElementById("magic-email-input");
const tokenInput = document.getElementById("magic-token-input");

const backendBaseUrl = window.BACKEND_BASE_URL || "http://127.0.0.1:8000";
const telegramBotUsername = window.TELEGRAM_BOT_USERNAME || "NitraTunnel_Bot";

function print(data) {
  output.textContent = typeof data === "string" ? data : JSON.stringify(data, null, 2);
}

async function postJson(path, payload) {
  const response = await fetch(`${backendBaseUrl}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify(payload),
  });
  const data = await response.json().catch(() => ({}));
  return { response, data };
}

async function loginWithTelegramPayload(user) {
  print("Verifying Telegram login...");
  try {
    const { response, data } = await postJson("/api/auth/telegram", user);
    if (!response.ok) {
      print({ error: `HTTP ${response.status}`, detail: data });
      return;
    }
    print(data);
    window.location.href = "/cabinet/";
  } catch (error) {
    print(
      `Request failed: ${String(error)}\n` +
        `Check backend availability: ${backendBaseUrl}`,
    );
  }
}

function renderTelegramWidget() {
  if (!telegramWidgetContainer) {
    return;
  }
  telegramWidgetContainer.innerHTML = "";
  const script = document.createElement("script");
  script.async = true;
  script.src = "https://telegram.org/js/telegram-widget.js?22";
  script.setAttribute("data-telegram-login", telegramBotUsername);
  script.setAttribute("data-size", "large");
  script.setAttribute("data-userpic", "false");
  script.setAttribute("data-request-access", "write");
  script.setAttribute("data-onauth", "onTelegramAuth(user)");
  telegramWidgetContainer.appendChild(script);
}

window.onTelegramAuth = async function onTelegramAuth(user) {
  await loginWithTelegramPayload(user);
};

telegramLoginButton?.addEventListener("click", () => {
  renderTelegramWidget();
  print("Telegram widget reloaded.");
});

requestMagicLinkButton?.addEventListener("click", async () => {
  const email = (emailInput?.value || "").trim();
  if (!email) {
    print("Email is required.");
    return;
  }

  print("Requesting magic link...");
  try {
    const { response, data } = await postJson("/api/auth/magic-link/request", { email });
    if (!response.ok) {
      print({ error: `HTTP ${response.status}`, detail: data });
      return;
    }
    print(data);
  } catch (error) {
    print(
      `Request failed: ${String(error)}\n` +
        `Check backend availability: ${backendBaseUrl}`,
    );
  }
});

verifyMagicLinkButton?.addEventListener("click", async () => {
  const token = (tokenInput?.value || "").trim();
  if (!token) {
    print("Token is required.");
    return;
  }

  print("Verifying token...");
  try {
    const { response, data } = await postJson("/api/auth/magic-link/verify", { token });
    if (!response.ok) {
      print({ error: `HTTP ${response.status}`, detail: data });
      return;
    }
    print(data);
    window.location.href = "/cabinet/";
  } catch (error) {
    print(
      `Request failed: ${String(error)}\n` +
        `Check backend availability: ${backendBaseUrl}`,
    );
  }
});

renderTelegramWidget();
