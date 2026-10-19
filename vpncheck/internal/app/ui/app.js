// The page of vpncheck's app. It only draws what /api/state says and sends
// the buttons back; the check, the files and the clipboard are all the app's.

const $ = (id) => document.getElementById(id);

// The key the app handed this page in the address (#k=...). Kept for a
// reload, and taken out of the address bar so it does not get copied along.
const token = (() => {
  const match = /(?:^#|&)k=([^&]+)/.exec(location.hash);
  let key = match ? decodeURIComponent(match[1]) : "";
  try {
    if (key) sessionStorage.setItem("vpncheck-key", key);
    else key = sessionStorage.getItem("vpncheck-key") || "";
  } catch {
    // Storage blocked: the key in hand still works until a reload.
  }
  if (match) history.replaceState(null, "", location.pathname);
  return key;
})();

async function api(path, body) {
  // The app's own window asks with no key: it is the app itself that
  // answers, not a port another page could reach.
  const options = { headers: token ? { Authorization: "Bearer " + token } : {} };
  if (body !== undefined) {
    options.method = "POST";
    options.headers["Content-Type"] = "application/json";
    options.body = JSON.stringify(body);
  }
  const response = await fetch(path, options);
  if (response.status === 401 || response.status === 403) {
    $("expired").hidden = false;
    throw new Error("unauthorized");
  }
  let data = null;
  try {
    data = await response.json();
  } catch {
    // Not JSON: a plain error page.
  }
  return { status: response.status, data };
}

// In the Android app the page reaches the phone through the app's own code
// (KairaAndroid): the clipboard, the system's dialog for saving a file, and
// the share sheet, which is how a file gets into Telegram there.
const phone = window.KairaAndroid || null;
if (phone) {
  $("copy-label").textContent = "Поделиться файлом";
  $("report-hint").textContent = "Через «Поделиться» отчёт можно сразу отправить в чат поддержки в Telegram.";
}

// The clipboard's subscription link, or the problem with what is there.
function clipboardLink() {
  return phone ? api("/api/paste", { text: phone.clipboard() || "" }) : api("/api/paste");
}

// Asked only on mobile data, where the box shows.
function checkBody(link) {
  return { link, speed: $("speed").checked };
}

function showProblem(box, problem) {
  box.hidden = !problem;
  if (!problem) return;
  box.querySelector("strong").textContent = problem.title;
  box.querySelector("span").textContent = problem.text;
}

let toastTimer = 0;
function toast(text) {
  const box = $("toast");
  box.textContent = text;
  box.hidden = false;
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => { box.hidden = true; }, 5000);
}

function plural(n, one, few, many) {
  const tens = n % 100, units = n % 10;
  if (tens >= 11 && tens <= 14) return many;
  if (units === 1) return one;
  if (units >= 2 && units <= 4) return few;
  return many;
}

// -- the first screen --------------------------------------------------------

let current = null;
let linkTouched = false;

$("link").addEventListener("input", () => {
  linkTouched = true;
  showProblem($("link-problem"), null);
});

$("link-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  $("start").disabled = true;
  try {
    const { status, data } = await api("/api/check", checkBody($("link").value));
    if (status !== 200) {
      showProblem($("link-problem"), data && data.problem);
      return;
    }
    render(data);
  } finally {
    $("start").disabled = false;
  }
});

$("paste").addEventListener("click", async () => {
  const { data } = await clipboardLink();
  if (data && data.link) {
    $("link").value = data.link;
    linkTouched = true;
    showProblem($("link-problem"), null);
  } else {
    showProblem($("link-problem"), data && data.problem);
  }
});

$("forget").addEventListener("click", async () => {
  const { data } = await api("/api/forget", {});
  $("link").value = "";
  linkTouched = false;
  render(data);
});

// -- the run screen ----------------------------------------------------------

$("stop").addEventListener("click", async () => {
  $("stop").disabled = true;
  render((await api("/api/stop", {})).data);
});

$("again").addEventListener("click", async () => {
  const { status, data } = await api("/api/check", checkBody((current && current.link) || $("link").value));
  if (status === 200) render(data);
  else toast(data && data.problem ? data.problem.title : "Не удалось начать проверку");
});

$("other").addEventListener("click", async () => {
  render((await api("/api/reset", {})).data);
  $("link").value = "";
  linkTouched = true;
  $("link").focus();
});

$("save").addEventListener("click", async () => {
  $("save").disabled = true;
  try {
    if (phone) {
      // The phone asks where to put it; the app says when it is saved.
      const { status, data } = await api("/api/report", {});
      if (status === 200) phone.save(data.name);
      else toast(data && data.problem ? data.problem.title + ". " + data.problem.text : "Не удалось сохранить отчёт");
      return;
    }
    const { status, data } = await api("/api/save", {});
    if (status === 200) toast("Сохранено: " + data.path);
    else toast(data && data.problem ? data.problem.title + ". " + data.problem.text : "Не удалось сохранить отчёт");
  } finally {
    $("save").disabled = false;
  }
});

$("send").addEventListener("click", async () => {
  $("send").disabled = true;
  try {
    const { status, data } = await api("/api/send", { note: $("note").value });
    if (status === 200) render(data);
    else toast(data && data.problem ? data.problem.title + ". " + data.problem.text : "Не удалось отправить");
  } finally {
    $("send").disabled = Boolean(current && current.sending);
  }
});

$("copy").addEventListener("click", async () => {
  $("copy").disabled = true;
  try {
    if (phone) {
      const { status, data } = await api("/api/report", {});
      if (status === 200) phone.share(data.name);
      else toast(data && data.problem ? data.problem.title + ". " + data.problem.text : "Не удалось поделиться файлом");
      return;
    }
    const { status, data } = await api("/api/copy", {});
    if (status === 200) {
      const keys = navigator.platform.startsWith("Mac") ? "Cmd+V" : "Ctrl+V";
      toast("Файл " + data.name + " скопирован. Вставьте его в чат поддержки в Telegram: " + keys + ".");
    } else {
      toast(data && data.problem ? data.problem.title + ". " + data.problem.text : "Не удалось скопировать файл");
    }
  } finally {
    $("copy").disabled = false;
  }
});

// The app's window opens no links itself; the app opens this one («Продлить»)
// in the browser. In a browser tab the link just opens.
$("fix").addEventListener("click", async (event) => {
  if (!current || !current.window) return;
  event.preventDefault();
  const { status, data } = await api("/api/open", {});
  if (status !== 204 && data && data.problem) toast(data.problem.title + ". " + data.problem.text);
});

// The list is built once per run and then only updated, so a server opened
// to read stays open while the check goes on.
let builtRun = -1;
const groupRows = [];
const serverRows = [];

function buildList(state) {
  const list = $("groups");
  list.replaceChildren();
  groupRows.length = 0;
  serverRows.length = 0;
  for (const group of state.groups || []) {
    const item = $("group-template").content.firstElementChild.cloneNode(true);
    item.querySelector(".group-name").textContent = group.name;
    const button = item.querySelector(".group-row");
    const servers = item.querySelector(".servers");
    button.addEventListener("click", () => {
      const open = button.getAttribute("aria-expanded") !== "true";
      button.setAttribute("aria-expanded", String(open));
      servers.hidden = !open;
    });
    for (const index of group.servers) {
      const server = state.servers[index];
      const row = $("server-template").content.firstElementChild.cloneNode(true);
      row.querySelector(".server-host").textContent = server.host + ":" + server.port;
      const rowButton = row.querySelector(".server-row");
      rowButton.addEventListener("click", () => toggleDetail(index, row));
      servers.append(row);
      (serverRows[index] ||= []).push(row);
    }
    list.append(item);
    groupRows.push(item);
  }
  $("groups-title").hidden = groupRows.length === 0;
  builtRun = state.run;
}

function serverEnd(server) {
  switch (server.state) {
    case "ok":
    case "warn":
      return server.ping ? server.ping + " мс" : "";
    case "bad":
      return "не работает";
    case "running":
      return "проверяю…";
  }
  return "";
}

function updateList(state) {
  (state.groups || []).forEach((group, i) => {
    const item = groupRows[i];
    if (!item) return;
    item.dataset.state = group.state;
    const total = group.servers.length;
    item.querySelector(".group-row .row-sub").textContent =
      total === 1 ? state.servers[group.servers[0]].kind : total + " " + plural(total, "сервер", "сервера", "серверов");
    let end = "";
    if (group.state === "ok") end = group.ping ? group.ping + " мс" : "";
    else if (group.state === "warn") end = "работает " + group.working + " из " + total;
    else if (group.state === "bad") end = "не работает";
    else if (group.state === "running") end = "проверяю…";
    item.querySelector(".group-row .row-end").textContent = end;
  });
  (state.servers || []).forEach((server, i) => {
    for (const row of serverRows[i] || []) {
      row.dataset.state = server.state;
      row.querySelector(".row-sub").textContent = server.note || server.kind;
      row.querySelector(".row-end").textContent = serverEnd(server);
    }
  });
}

async function toggleDetail(index, row) {
  const button = row.querySelector(".server-row");
  const box = row.querySelector(".detail");
  const open = button.getAttribute("aria-expanded") !== "true";
  button.setAttribute("aria-expanded", String(open));
  box.hidden = !open;
  if (!open) return;
  box.textContent = "Загружаю…";
  const { status, data } = await api("/api/server/" + index);
  if (status !== 200) {
    box.textContent = "Нет данных.";
    return;
  }
  drawDetail(box, data);
}

function el(tag, className, text) {
  const node = document.createElement(tag);
  if (className) node.className = className;
  if (text !== undefined) node.textContent = text;
  return node;
}

function drawDetail(box, d) {
  box.replaceChildren();
  const facts = [d.kind];
  if (d.sni) facts.push("SNI " + d.sni);
  if (d.profiles && d.profiles.length) facts.push("профили: " + d.profiles.join(", "));
  box.append(el("p", "facts-line", facts.join(" · ")));
  if (!d.steps || !d.steps.length) {
    box.append(el("p", "facts-line", "Ещё не проверен."));
    return;
  }
  const steps = el("ul", "steps");
  for (const step of d.steps) {
    const li = el("li");
    li.dataset.state = step.status;
    const text = el("div");
    text.append(el("div", "step-name", step.name), el("div", "step-detail", step.detail));
    li.append(el("span", "dot"), text);
    steps.append(li);
  }
  box.append(steps);
  if (d.hints && d.hints.length) {
    const hints = el("div", "hints");
    for (const hint of d.hints) hints.append(el("p", "", hint));
    box.append(hints);
  }
  if (d.exit) box.append(el("p", "facts-line", "Выход в интернет: " + d.exit));
  if (d.log && d.log.length) {
    const details = el("details");
    details.append(el("summary", "", "Лог Xray для поддержки"), el("pre", "", d.log.join("\n")));
    box.append(details);
  }
}

// -- drawing the state -------------------------------------------------------

const busy = new Set(["fetching", "network", "tunnels"]);

function render(state) {
  if (!state) return;
  current = state;
  $("version").textContent = state.version ? "версия " + state.version : "";
  $("vpn-warning").hidden = !state.vpn;

  const idle = state.phase === "idle";
  $("screen-link").hidden = !idle;
  $("screen-run").hidden = idle;
  if (idle) {
    if (!linkTouched && state.link && !$("link").value) $("link").value = state.link;
    $("remembered").hidden = !state.link;
    $("speed-choice").hidden = !state.metered;
    builtRun = -1;
    return;
  }
  const card = state.card;
  $("card").hidden = !card;
  if (card) {
    $("card-title").textContent = card.title;
    $("card-status").textContent = card.status || "";
    $("card-status").hidden = !card.status;
    $("card-status").dataset.tone = card.tone || "";
    const meta = [];
    if (card.servers) meta.push(card.servers + " " + plural(card.servers, "сервер", "сервера", "серверов") +
      " в " + card.profiles + " " + plural(card.profiles, "профиле", "профилях", "профилях"));
    if (card.traffic) meta.push(card.traffic);
    $("card-meta").textContent = meta.join(" · ");
    $("card-note").textContent = card.note || "";
    $("card-note").hidden = !card.note;
  }

  const running = busy.has(state.phase);
  $("progress").hidden = !running;
  $("result").hidden = running;
  if (running) {
    $("stop").disabled = false;
    const p = state.progress;
    if (state.phase === "fetching" || !p) {
      $("progress-label").textContent = "Скачиваю подписку…";
      $("progress-count").textContent = "";
      $("bar-fill").style.width = "4%";
      $("progress-current").textContent = "";
    } else {
      $("progress-label").textContent = state.phase === "network" ? "Проверяю сеть до серверов…" : "Подключаюсь к серверам";
      $("progress-count").textContent = p.done + " из " + p.total;
      $("bar-fill").style.width = Math.max(4, p.percent) + "%";
      $("progress-current").textContent = p.current ? "Сейчас: " + p.current : "";
    }
  } else {
    drawResult(state);
  }

  if (state.run !== builtRun && state.groups) buildList(state);
  if (!state.groups) {
    $("groups").replaceChildren();
    $("groups-title").hidden = true;
  }
  updateList(state);
}

function drawResult(state) {
  const sum = state.summary;
  $("result-count").hidden = !sum;
  $("result-line").hidden = !sum;
  if (sum) {
    $("result-count").textContent = sum.works === sum.total && sum.total > 0
      ? "Работают все " + sum.total
      : "Работают " + sum.works + " из " + sum.total;
    $("result-count").dataset.tone = sum.tone;
    $("result-line").textContent = sum.line;
  }
  showProblem($("failure"), state.problem);
  const fix = state.problem && state.problem.link;
  $("fix").hidden = !fix;
  if (fix) {
    $("fix").href = state.problem.link;
    $("fix").textContent = state.problem.link_text || "Открыть";
  }

  // Sending is the main way out once it is possible; saving and copying stay
  // for Telegram, where support is too.
  const sent = state.sent;
  $("send-block").hidden = !state.can_send || Boolean(sent);
  $("send").disabled = Boolean(state.sending);
  $("sent").hidden = !sent;
  if (sent) {
    $("sent-title").textContent = (sent.created ? "Открыто обращение №" : "Отправлено в обращение №") + sent.ticket_id;
  }
  // One main button: sending, or the way out of the problem when there is one.
  $("save").className = (state.can_send && !sent) || fix ? "secondary" : "primary";
  $("report-actions").hidden = !state.report;
  $("report-hint").hidden = !state.report;
}

// -- polling -----------------------------------------------------------------

async function poll() {
  try {
    const { status, data } = await api("/api/state");
    if (status === 200) render(data);
  } catch {
    // The app was closed, or the key was refused; the banner says which.
  }
  const fast = current && busy.has(current.phase) && !document.hidden;
  setTimeout(poll, fast ? 500 : 1500);
}

async function offerClipboard() {
  // A link the customer has just copied goes straight into the field.
  if ($("link").value) return;
  try {
    const { data } = await clipboardLink();
    if (data && data.link && !$("link").value) $("link").value = data.link;
  } catch {
    // Nothing to offer.
  }
}

(async () => {
  await poll();
  if (current && current.phase === "idle" && !current.link) offerClipboard();
})();
