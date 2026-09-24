/*
 * Support: the customer's tickets, one ticket's thread, and the two forms that
 * write to them.
 *
 * The page only ever talks to our own API. Getting a ticket in front of an
 * operator is admin_bot's job -- it reads what the API stored and forwards it
 * to Telegram -- so all this page needs to know is whether the section is
 * switched on.
 *
 * Everything shown goes through textContent or element properties. Subjects,
 * messages and file names are the customer's own text, and the operators'
 * answers come from a Telegram chat; none of it is markup.
 */

import { boot, hydrateIcons, clientConfig } from "./app.js";
import {
  $,
  api,
  ApiError,
  el,
  flash,
  clearFlash,
  formatDate,
  icon,
  show,
  toLogin,
  withBusy,
} from "./core.js";
import {
  ACCEPT,
  checkFiles,
  formatSize,
  statusView,
  ticketFromSearch,
} from "./support-files.js";

/** How often an open thread looks for an answer, while the tab is visible. */
const POLL_MS = 20_000;

const stampFormat = new Intl.DateTimeFormat("ru-RU", {
  day: "2-digit",
  month: "2-digit",
  hour: "2-digit",
  minute: "2-digit",
});

function stamp(unixSeconds) {
  return stampFormat.format(new Date(unixSeconds * 1000));
}

function failed(err, fallback) {
  if (err instanceof ApiError && err.status === 401) {
    toLogin();
    return;
  }
  flash(err instanceof ApiError ? err.message : fallback);
}

// -- sending --------------------------------------------------------------

/**
 * Posts a form and reports upload progress, which fetch cannot do.
 *
 * A 45 MB screen recording over a phone's uplink takes minutes. A button that
 * says nothing for that long reads as broken, and gets pressed again.
 */
function send(path, data, meter) {
  return new Promise((resolve, reject) => {
    const xhr = new XMLHttpRequest();
    xhr.open("POST", path);
    xhr.responseType = "json";

    const bar = meter?.firstElementChild;
    if (bar) {
      // Through the CSSOM: the policy forbids style attributes, not this.
      bar.style.width = "0%";
      show(meter, true);
      xhr.upload.addEventListener("progress", (event) => {
        if (event.lengthComputable) {
          bar.style.width = `${Math.round((event.loaded / event.total) * 100)}%`;
        }
      });
    }
    xhr.addEventListener("loadend", () => show(meter, false));
    xhr.addEventListener("load", () => {
      const payload = xhr.response;
      if (xhr.status >= 200 && xhr.status < 300) {
        resolve(payload);
        return;
      }
      // A 413 from the proxy in front of us is its own HTML page, with none
      // of our JSON in it -- so the message has to be supplied here.
      const message =
        payload?.message ||
        (xhr.status === 413 ? "Файлы слишком большие для отправки." : undefined);
      reject(new ApiError(xhr.status, payload?.error, message));
    });
    xhr.addEventListener("error", () => {
      reject(new ApiError(0, "offline", "Нет связи с сервером. Проверьте подключение."));
    });
    xhr.send(data);
  });
}

/**
 * Keeps a form's chosen files, and the chips that show them.
 *
 * Picking again adds to the selection rather than replacing it: somebody who
 * attaches a screenshot and then goes back for the log expects both, and the
 * operating system's picker, left alone, keeps only the second.
 */
function filePicker(form) {
  const input = $("[data-file-input]", form);
  const list = $("[data-file-list]", form);
  input.accept = ACCEPT;
  let files = [];

  const render = () => {
    list.textContent = "";
    files.forEach((file, index) => {
      const remove = el("button", {
        class: "chip-remove",
        type: "button",
        "aria-label": `Убрать ${file.name}`,
      });
      remove.append(icon("close"));
      remove.addEventListener("click", () => {
        files.splice(index, 1);
        render();
      });
      list.append(
        el("li", { class: "file-chip" }, [
          icon("file"),
          el("span", { class: "file-name", text: file.name }),
          el("span", { class: "muted", text: formatSize(file.size) }),
          remove,
        ])
      );
    });
  };

  input.addEventListener("change", () => {
    const next = [...files, ...input.files];
    // Cleared so that picking the same file again, after removing it, still
    // counts as a change.
    input.value = "";
    const problem = checkFiles(next);
    if (problem) {
      flash(problem);
      return;
    }
    clearFlash();
    files = next;
    render();
  });

  return {
    get files() {
      return files;
    },
    clear() {
      files = [];
      render();
    },
  };
}

// -- the list ---------------------------------------------------------------

function renderTickets(tickets) {
  const list = $("[data-ticket-list]");
  list.textContent = "";
  $("[data-ticket-summary]").textContent = tickets.length
    ? `Обращений: ${tickets.length}`
    : "Обращений пока нет.";

  for (const ticket of tickets) {
    const status = statusView(ticket.status);
    list.append(
      el("li", {}, [
        el(
          "a",
          {
            class: "ticket-row",
            href: `/app/support?id=${ticket.id}`,
            "data-unread": ticket.unread,
            "data-status": ticket.status,
          },
          [
            el("span", { class: "ticket-main" }, [
              el("span", { class: "strong ticket-subject", text: ticket.subject }),
              el("span", {
                class: "mono-sm muted",
                text: `#${ticket.id} · ${formatDate(ticket.updated_at)}`,
              }),
            ]),
            ticket.unread ? el("span", { class: "unread-dot", title: "Новый ответ" }) : null,
            el("span", { class: "badge", "data-kind": status.kind || undefined, text: status.label }),
          ]
        ),
      ])
    );
  }
}

function openNewForm() {
  const form = $("[data-new-form]");
  show(form, true);
  show($("[data-new-ticket]"), false);
  $("#ticket-subject").focus();
}

function closeNewForm(picker) {
  const form = $("[data-new-form]");
  form.reset();
  picker.clear();
  show(form, false);
  show($("[data-new-ticket]"), true);
}

async function submitNew(event, picker) {
  event.preventDefault();
  clearFlash();
  const form = event.currentTarget;
  const subject = $("#ticket-subject");
  const body = $("#ticket-body");

  subject.removeAttribute("aria-invalid");
  body.removeAttribute("aria-invalid");
  if (subject.value.trim().length < 3) {
    subject.setAttribute("aria-invalid", "true");
    flash("Коротко опишите тему обращения.");
    return;
  }
  if (!body.value.trim()) {
    body.setAttribute("aria-invalid", "true");
    flash("Опишите, что случилось.");
    return;
  }

  const data = new FormData();
  data.append("subject", subject.value.trim());
  data.append("body", body.value.trim());
  for (const file of picker.files) data.append("files", file, file.name);

  await withBusy($("[data-submit]", form), async () => {
    try {
      const created = await send("/api/support/tickets", data, $("[data-progress]", form));
      location.assign(`/app/support?id=${created.id}`);
    } catch (err) {
      failed(err, "Не удалось отправить обращение.");
    }
  });
}

async function showList() {
  show($("[data-list-view]"), true);
  const picker = filePicker($("[data-new-form]"));

  $("[data-new-ticket]").addEventListener("click", openNewForm);
  $("[data-cancel]").addEventListener("click", () => closeNewForm(picker));
  $("[data-new-form]").addEventListener("submit", (event) => submitNew(event, picker));

  const { tickets } = await api("/api/support/tickets");
  renderTickets(tickets);
  // With nothing to list, the form is the only thing on the page worth
  // doing -- and "create a new one" from a closed ticket lands here asking
  // for exactly that.
  if (!tickets.length || new URLSearchParams(location.search).has("new")) {
    openNewForm();
  }
}

// -- one ticket ---------------------------------------------------------------

function renderAttachment(attachment) {
  if (!attachment.available) {
    return el("span", { class: "file-chip muted" }, [
      icon("file"),
      el("span", { class: "file-name", text: attachment.name }),
      el("span", { text: "удалён по сроку хранения" }),
    ]);
  }
  if (attachment.kind === "image") {
    return el("a", { class: "file-thumb", href: attachment.url, target: "_blank", rel: "noopener" }, [
      el("img", { src: attachment.url, alt: attachment.name, loading: "lazy" }),
    ]);
  }
  if (attachment.kind === "video") {
    // preload=metadata: the first frame and the length, not the recording.
    return el("video", {
      class: "file-video",
      src: attachment.url,
      controls: true,
      preload: "metadata",
      playsinline: true,
    });
  }
  return el("a", { class: "file-chip", href: attachment.url, download: attachment.name }, [
    icon("download"),
    el("span", { class: "file-name", text: attachment.name }),
    el("span", { class: "muted", text: formatSize(attachment.size) }),
  ]);
}

function renderMessage(message, isNew) {
  const mine = message.author === "user";
  return el("li", { class: "msg", "data-author": mine ? "user" : "support", "data-new": isNew }, [
    el("div", { class: "msg-head mono-sm" }, [
      el("span", { class: mine ? "strong" : "accent", text: mine ? "Вы" : "Поддержка" }),
      el("span", { class: "muted", text: stamp(message.created_at) }),
    ]),
    message.body ? el("p", { class: "msg-body", text: message.body }) : null,
    message.attachments.length
      ? el("div", { class: "msg-files" }, message.attachments.map(renderAttachment))
      : null,
  ]);
}

/**
 * Draws the thread. Answers the customer has not seen yet -- the ones after
 * their own last message, when the ticket came back flagged unread -- are
 * marked, so the eye lands on what changed.
 */
function renderThread({ ticket, messages }) {
  $("[data-thread-subject]").textContent = ticket.subject;
  const status = statusView(ticket.status);
  const badge = $("[data-thread-status]");
  badge.textContent = status.label;
  if (status.kind) badge.dataset.kind = status.kind;
  else delete badge.dataset.kind;
  show(badge, true);
  $("[data-thread-meta]").textContent = `#${ticket.id} · открыто ${formatDate(ticket.created_at)}`;

  let lastOwn = -1;
  messages.forEach((message, index) => {
    if (message.author === "user") lastOwn = index;
  });
  const thread = $("[data-thread]");
  thread.textContent = "";
  messages.forEach((message, index) => {
    thread.append(renderMessage(message, ticket.unread && index > lastOwn));
  });

  const closed = ticket.status === "closed";
  show($("[data-reply-form]"), !closed);
  show($("[data-closed-note]"), closed);
  hydrateIcons();
}

async function submitReply(event, id, picker, refresh) {
  event.preventDefault();
  clearFlash();
  const form = event.currentTarget;
  const body = $("#reply-body");
  if (!body.value.trim() && !picker.files.length) {
    flash("Напишите сообщение или приложите файл.");
    return;
  }

  const data = new FormData();
  data.append("body", body.value.trim());
  for (const file of picker.files) data.append("files", file, file.name);

  await withBusy($("[data-submit]", form), async () => {
    try {
      await send(`/api/support/tickets/${id}/messages`, data, $("[data-progress]", form));
      body.value = "";
      picker.clear();
      await refresh();
      $("[data-thread]").lastElementChild?.scrollIntoView({ block: "nearest" });
    } catch (err) {
      failed(err, "Не удалось отправить сообщение.");
    }
  });
}

async function closeTicket(id, button, refresh) {
  const confirmed = confirm(
    "Закрыть обращение?\n\nНаписать в него больше не получится — только создать новое."
  );
  if (!confirmed) return;
  await withBusy(button, async () => {
    try {
      await api(`/api/support/tickets/${id}/close`, { method: "POST" });
      await refresh();
      flash("Обращение закрыто.", "ok");
    } catch (err) {
      failed(err, "Не удалось закрыть обращение.");
    }
  });
}

async function showThread(id) {
  show($("[data-thread-view]"), true);

  let drawn = "";
  let sending = false;
  const refresh = async () => {
    const data = await api(`/api/support/tickets/${id}`);
    // Redrawn only when something changed, so a poll cannot restart a video
    // the customer is halfway through watching.
    const shape = `${data.ticket.status}:${data.messages.length}`;
    if (shape !== drawn) {
      renderThread(data);
      drawn = shape;
    }
  };

  try {
    await refresh();
  } catch (err) {
    if (err instanceof ApiError && err.status === 404) {
      $("[data-thread-subject]").textContent = "Обращение не найдено";
      return;
    }
    throw err;
  }

  const form = $("[data-reply-form]");
  const picker = filePicker(form);
  form.addEventListener("submit", async (event) => {
    sending = true;
    try {
      await submitReply(event, id, picker, refresh);
    } finally {
      sending = false;
    }
  });
  const close = $("[data-close-ticket]");
  close.addEventListener("click", () => closeTicket(id, close, refresh));

  setInterval(async () => {
    if (document.visibilityState !== "visible" || sending) return;
    try {
      await refresh();
    } catch (err) {
      // A missed poll is not worth a notice; the next one will try again.
      console.error("support poll", err);
    }
  }, POLL_MS);
}

// -- boot -----------------------------------------------------------------

boot(async (user) => {
  const config = await clientConfig();
  if (!config.support_enabled) {
    show($("[data-support-off]"), true);
    hydrateIcons();
    return;
  }
  show($("[data-tg-on]"), user.has_telegram);
  show($("[data-tg-off]"), !user.has_telegram && Boolean(config.telegram_bot));

  const id = ticketFromSearch(location.search);
  if (id) await showThread(id);
  else await showList();
  hydrateIcons();
});
