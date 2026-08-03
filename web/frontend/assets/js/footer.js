/*
 * The footer every page carries: what we have published, and how to reach us.
 *
 * The document links are already right in the markup — they are pages of this
 * site now — so a visitor with JavaScript blocked still gets both, and a legal
 * document remains readable with no script at all. This only *overrides* them
 * when .env names something else, which is what keeps the agreement the site
 * links to and the agreement the bot links to the same document.
 *
 * Support is the one entry markup cannot know: it is a Telegram URL that lives
 * only in configuration.
 *
 * Loaded as its own module script rather than folded into each page's entry
 * point, because the pages that most need a way out — 404, and the two
 * token-redeeming pages — have no entry point of their own.
 */

import { $$, clientConfig } from "./core.js";

clientConfig().then((config) => {
  for (const link of $$("[data-doc]")) {
    const url = config.docs?.[link.dataset.doc];
    // Only when configured. An empty value must not blank an href that
    // already points at a page we serve.
    if (url) link.href = url;
  }

  // Every one of them, not the first: the profile page has a "написать в
  // поддержку" link of its own above the footer, and matching only one would
  // leave whichever came second permanently hidden.
  for (const support of $$("[data-support]")) {
    if (!config.support_url) continue;
    support.href = config.support_url;
    support.rel = "noopener";
    support.hidden = false;
  }
});
