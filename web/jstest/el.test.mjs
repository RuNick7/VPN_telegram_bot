/*
 * Tests for el(), the one function every rendered element goes through.
 *
 * It needs a DOM, so there is a minimal fake below rather than a dependency:
 * the parts under test are attribute writing and the refusal to set raw HTML,
 * and neither needs a real element to be checked.
 *
 * Run: node --test web/jstest/
 */

import test from "node:test";
import assert from "node:assert/strict";

globalThis.document = {
  createElement(tag) {
    return {
      tagName: tag.toUpperCase(),
      attributes: {},
      children: [],
      className: "",
      textContent: "",
      setAttribute(name, value) {
        this.attributes[name] = value;
      },
      getAttribute(name) {
        return name in this.attributes ? this.attributes[name] : null;
      },
      addEventListener(type, handler) {
        this.listeners ||= {};
        this.listeners[type] = handler;
      },
      append(...nodes) {
        this.children.push(...nodes);
      },
    };
  },
};

const { el } = await import("../frontend/assets/js/core.js");

test("a true attribute is written as the string the stylesheet looks for", () => {
  // Every selector in app.css reads [data-x="true"]. Writing the HTML boolean
  // convention -- an empty value -- matched none of them, which left three
  // things silently inert: the device pips never lit up, the best-value plan
  // was never highlighted, and a spent gift was never dimmed.
  const node = el("span", { "data-on": true });
  assert.equal(node.getAttribute("data-on"), "true");
});

test("a false attribute is left off entirely", () => {
  // Not "false": `[data-on]` is a perfectly ordinary selector for somebody to
  // reach for later, and an attribute that is present but says false would
  // match it.
  const node = el("span", { "data-on": false });
  assert.equal(node.getAttribute("data-on"), null);
});

test("undefined and null are left off too", () => {
  const node = el("span", { "data-a": undefined, "data-b": null });
  assert.equal(node.getAttribute("data-a"), null);
  assert.equal(node.getAttribute("data-b"), null);
});

test("numbers and strings are written as given", () => {
  const node = el("input", { value: "GIFT-ABC123", tabindex: -1 });
  assert.equal(node.getAttribute("value"), "GIFT-ABC123");
  assert.equal(node.getAttribute("tabindex"), "-1");
});

test("class and text are properties, not attributes", () => {
  const node = el("p", { class: "mono-sm muted", text: "привет" });
  assert.equal(node.className, "mono-sm muted");
  assert.equal(node.textContent, "привет");
  assert.equal(node.getAttribute("class"), null);
});

test("raw HTML is refused rather than escaped", () => {
  // The one rule the whole frontend rests on: nothing from the server is ever
  // parsed as markup, so a stored email or Telegram tag cannot become script.
  assert.throws(() => el("div", { html: "<img onerror=alert(1)>" }), /raw HTML/);
});

test("falsy children are skipped so a conditional child needs no wrapper", () => {
  const node = el("div", {}, [el("span"), null, false, undefined]);
  assert.equal(node.children.length, 1);
});
