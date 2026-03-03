const output = document.getElementById("output");
const refreshButton = document.getElementById("refresh-btn");
const meView = document.getElementById("me-view");
const subscriptionView = document.getElementById("subscription-view");
const paymentView = document.getElementById("payment-view");
const tariffButtons = document.querySelectorAll(".tariff-btn");
const backendBaseUrl = window.BACKEND_BASE_URL || "http://127.0.0.1:8000";
const terminalPaymentStatuses = new Set(["succeeded", "failed", "processing_error"]);
let paymentPollingTimer = null;

function print(data) {
  output.textContent = typeof data === "string" ? data : JSON.stringify(data, null, 2);
}

async function getJson(path) {
  const response = await fetch(`${backendBaseUrl}${path}`, {
    method: "GET",
    credentials: "include",
  });
  const data = await response.json().catch(() => ({}));
  return { response, data };
}

async function postJson(path, payload) {
  const response = await fetch(`${backendBaseUrl}${path}`, {
    method: "POST",
    credentials: "include",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(payload),
  });
  const data = await response.json().catch(() => ({}));
  return { response, data };
}

function renderMe(me) {
  meView.textContent =
    `telegram_id: ${me.telegram_id ?? "-"}\n` +
    `username: ${me.username ?? "-"}\n` +
    `first_name: ${me.first_name ?? "-"}\n` +
    `last_name: ${me.last_name ?? "-"}\n` +
    `email: ${me.email ?? "-"}`;
}

function renderSubscription(subscription) {
  subscriptionView.textContent =
    `is_active: ${String(subscription.is_active)}\n` +
    `expire_at: ${subscription.expire_at ?? "-"}\n` +
    `subscription_ends: ${subscription.subscription_ends ?? "-"}\n` +
    `subscription_url: ${subscription.subscription_url || "-"}\n` +
    `panel_user_exists: ${String(subscription.panel_user_exists ?? false)}`;
}

function renderPayment(payment) {
  paymentView.textContent =
    `payment_id: ${payment.payment_id ?? "-"}\n` +
    `status: ${payment.status ?? "-"}\n` +
    `local_status: ${payment.local_status ?? "-"}\n` +
    `days_to_extend: ${payment.metadata?.days_to_extend ?? "-"}\n` +
    `confirmation_url: ${payment.confirmation_url || "-"}`;
}

async function loadCabinetData() {
  print("Loading cabinet data...");
  try {
    const meResult = await getJson("/api/me");
    if (!meResult.response.ok) {
      print({ endpoint: "/api/me", status: meResult.response.status, detail: meResult.data });
      return;
    }
    renderMe(meResult.data);

    const subscriptionResult = await getJson("/api/subscription");
    if (!subscriptionResult.response.ok) {
      subscriptionView.textContent = `Failed to load: HTTP ${subscriptionResult.response.status}`;
      print({ endpoint: "/api/subscription", detail: subscriptionResult.data });
      return;
    }
    renderSubscription(subscriptionResult.data);
    print("Cabinet data loaded.");
  } catch (error) {
    print(`Request failed: ${String(error)}`);
  }
}

function stopPaymentPolling() {
  if (paymentPollingTimer) {
    clearTimeout(paymentPollingTimer);
    paymentPollingTimer = null;
  }
}

async function pollPayment(paymentId, attempt = 1) {
  try {
    const paymentResult = await getJson(`/api/payments/${encodeURIComponent(paymentId)}`);
    if (!paymentResult.response.ok) {
      paymentView.textContent = `Failed to load payment: HTTP ${paymentResult.response.status}`;
      print({ endpoint: `/api/payments/${paymentId}`, detail: paymentResult.data });
      return;
    }

    renderPayment(paymentResult.data);
    const status = String(paymentResult.data.status || "").toLowerCase();
    if (terminalPaymentStatuses.has(status)) {
      print(`Payment ${paymentId} reached terminal status: ${status}`);
      stopPaymentPolling();
      return;
    }

    if (attempt >= 60) {
      print(`Stopped polling payment ${paymentId}: attempts limit reached.`);
      stopPaymentPolling();
      return;
    }

    paymentPollingTimer = setTimeout(() => {
      pollPayment(paymentId, attempt + 1);
    }, 3000);
  } catch (error) {
    print(`Payment polling failed: ${String(error)}`);
  }
}

function startPaymentPollingFromQuery() {
  stopPaymentPolling();
  const params = new URLSearchParams(window.location.search);
  const paymentId = (params.get("payment_id") || "").trim();
  if (!paymentId) {
    paymentView.textContent = "No payment selected.";
    return;
  }
  paymentView.textContent = `Polling payment ${paymentId} ...`;
  pollPayment(paymentId);
}

async function startExtendFlow(months) {
  print(`Creating payment for ${months} month(s)...`);
  try {
    const returnUrl = `${window.location.origin}/cabinet/`;
    const { response, data } = await postJson("/api/subscription/extend", {
      months,
      return_url: returnUrl,
    });
    if (!response.ok) {
      print({ endpoint: "/api/subscription/extend", status: response.status, detail: data });
      return;
    }

    const paymentId = data.payment_id;
    const confirmationUrl = data.confirmation_url;
    if (!paymentId || !confirmationUrl) {
      print({ error: "Invalid extend response", detail: data });
      return;
    }

    localStorage.setItem("lastPaymentId", String(paymentId));
    const redirectUrl = new URL(String(confirmationUrl));
    redirectUrl.searchParams.set("return", `${window.location.origin}/cabinet/?payment_id=${encodeURIComponent(paymentId)}`);
    window.location.href = redirectUrl.toString();
  } catch (error) {
    print(`Extend flow failed: ${String(error)}`);
  }
}

refreshButton?.addEventListener("click", async () => {
  await loadCabinetData();
  startPaymentPollingFromQuery();
});

tariffButtons.forEach((button) => {
  button.addEventListener("click", async () => {
    const monthsRaw = button.getAttribute("data-months") || "";
    const months = Number(monthsRaw);
    if (!Number.isInteger(months) || ![1, 3, 6, 12].includes(months)) {
      print(`Unsupported months value: ${monthsRaw}`);
      return;
    }
    await startExtendFlow(months);
  });
});

loadCabinetData();
startPaymentPollingFromQuery();
