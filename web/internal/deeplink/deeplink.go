// Package deeplink hands a subscription over to the app it belongs in.
//
// Telegram does not render `happ://…` as a link at all -- an app scheme is not
// something it recognises -- so the one-tap import step in the bot's setup
// instructions has to be an ordinary https:// URL that turns into one. This is
// that URL: `/auto?url=happ://add/https://sub.example.com/<token>` answers with
// a redirect to whatever `url` holds.
//
// It used to be somebody else's server. That worked, and it meant every
// customer's subscription URL -- which is the credential, whole and sufficient
// to configure their VPN -- travelled through a third party on the way to their
// own phone.
package deeplink

import (
	"errors"
	"log/slog"
	"net/http"
	"strings"
)

// allowedSchemes is what this endpoint will hand a visitor off to.
//
// The list is the entire difference between a deep-link helper and an open
// redirector. Without it `https://kairavpn.pro/auto/?url=https://not-us.example`
// is a phishing link wearing our own domain -- and the domain is precisely the
// part people are told to check before they trust a link.
//
// So `http` and `https` are absent, and should stay absent. Every entry is a
// decision about what this domain will vouch for, which is why they are listed
// by hand rather than matched by a pattern.
//
// The bot picks the scheme (`user_bot/handlers/setup.py`, `_auto_import_link`).
// Nothing can check the two lists against each other across languages, so a new
// client app means editing both -- the symptom of forgetting is a setup button
// that answers 400.
var allowedSchemes = map[string]bool{
	"happ": true,
}

// ErrNotAppLink covers every reason a `url` parameter is refused. One error
// rather than several: the answer to the caller is the same in each case, and
// the distinctions are only interesting from the inside.
var ErrNotAppLink = errors.New("deeplink: not a link to a known app")

// Target checks a `url` parameter and returns what to redirect to.
//
// The value is returned **byte for byte**, never re-serialised. It is tempting
// to run it through net/url and hand back `u.String()`, and that quietly breaks
// the only shape this endpoint ever sees: the payload of `happ://add/` is
// itself a URL, and parsing collapses the `//` in `https://sub…` on the way
// back out. The app is then handed `https:/sub…` and imports nothing.
func Target(raw string) (string, error) {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return "", ErrNotAppLink
	}

	// A header value is one line by definition. Anything carrying a control
	// character is corrupt or is trying to write a second header, and Go would
	// drop the whole thing later anyway -- better to refuse it here, where the
	// reason is visible.
	if strings.ContainsAny(raw, "\r\n\x00") {
		return "", ErrNotAppLink
	}

	scheme, rest, found := strings.Cut(raw, ":")
	if !found || rest == "" {
		// No scheme at all. Catches `//evil.example`, which a browser reads as
		// a protocol-relative URL and would follow off this site.
		return "", ErrNotAppLink
	}
	if !allowedSchemes[strings.ToLower(scheme)] {
		return "", ErrNotAppLink
	}
	return raw, nil
}

// Handler answers /auto.
func Handler(log *slog.Logger) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		if r.Method != http.MethodGet && r.Method != http.MethodHead {
			w.Header().Set("Allow", "GET, HEAD")
			http.Error(w, "Method Not Allowed", http.StatusMethodNotAllowed)
			return
		}

		header := w.Header()
		// The subscription URL sits in the query string, and it is the whole
		// credential: anyone holding it can configure the VPN as this customer.
		// So no shared cache keeps a copy of the redirect, and nothing this
		// hands off to learns where it came from.
		header.Set("Cache-Control", "no-store")
		header.Set("Referrer-Policy", "no-referrer")
		header.Set("X-Content-Type-Options", "nosniff")

		target, err := Target(r.URL.Query().Get("url"))
		if err != nil {
			// Neither the log line nor the reply repeats what was asked for.
			// The parameter is a credential on the ordinary path and attacker
			// text on this one, and neither belongs in a log file or on a page.
			log.Warn("deeplink refused", "remote", r.RemoteAddr)
			http.Error(w, "Ссылка не похожа на ссылку для приложения.", http.StatusBadRequest)
			return
		}

		// Written by hand rather than through http.Redirect, which would add an
		// HTML body repeating the customer's subscription URL and percent-escape
		// a Location this one needs verbatim.
		header.Set("Location", target)
		w.WriteHeader(http.StatusFound)
	})
}
