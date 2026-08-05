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

import { $$, clientConfig, copyText } from "./core.js";

/*
 * The support address copies instead of navigating.
 *
 * `mailto:` is the obvious markup and the wrong one on a desktop with no mail
 * client configured, which is most of them: clicking opened a blank browser
 * tab or an app chooser, and the address stayed exactly where it was. Copying
 * is what somebody clicking an address in a footer actually wants.
 *
 * The label swaps to confirm, because a copy that gives no feedback is
 * indistinguishable from a click that did nothing -- the very complaint this
 * replaces.
 */
for (const button of $$("[data-copy-mail]")) {
  button.addEventListener("click", async () => {
    const original = button.textContent;
    if (await copyText(button.dataset.copyMail, button)) {
      button.textContent = "Скопировано";
      setTimeout(() => {
        button.textContent = original;
      }, 1600);
      return;
    }
    // The clipboard can be refused -- a browser that wants a gesture it did
    // not see, a page that is not focused. Selecting the address leaves the
    // customer one keystroke from having it, rather than back where they
    // started with a control that did nothing.
    const range = document.createRange();
    range.selectNodeContents(button);
    const selection = window.getSelection();
    selection?.removeAllRanges();
    selection?.addRange(range);
  });
}

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

  // Same rule as support: shown only when there is an address behind it, so a
  // deployment without a channel does not offer one.
  for (const channel of $$("[data-channel]")) {
    if (!config.channel_url) continue;
    channel.href = config.channel_url;
    channel.rel = "noopener";
    channel.hidden = false;
  }
});
