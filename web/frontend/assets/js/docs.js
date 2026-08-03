/*
 * The legal documents.
 *
 * They are static HTML and must render with no script at all — the text is the
 * point, and a customer reading the refund policy with JavaScript blocked is
 * reading the whole of it.
 *
 * So this fills in exactly one thing the page cannot know about itself: where
 * support lives. The revision date is deliberately *not* here. Taken from
 * `Last-Modified` it would show the last deploy rather than the last edit, and
 * a legal document that claims to have been revised on a day its text did not
 * change is worse than one with no date on it.
 */

import { $, clientConfig } from "./core.js";

clientConfig().then((config) => {
  const support = $("[data-support]");
  if (support && config.support_url) {
    support.href = config.support_url;
    support.rel = "noopener";
    support.hidden = false;
  }
});
