package api

import (
	"testing"

	"github.com/RuNick7/VPN_telegram_bot/web/internal/config"
)

func TestReturnURLRefusesToRedirectOffSite(t *testing.T) {
	// YooKassa sends the user back here after paying. Honouring a full URL
	// from the client would make this an open redirect -- and one arriving at
	// the end of a real payment flow, which is exactly when someone is primed
	// to trust the page they land on.
	server := &Server{cfg: &config.Config{BaseURL: "https://cabinet.example.com"}}

	hostile := []string{
		"https://evil.example.com/",
		"//evil.example.com/",
		"http://evil.example.com",
		"javascript:alert(1)",
		"",
	}
	for _, requested := range hostile {
		if got := server.returnURL(requested); got != "https://cabinet.example.com/" {
			t.Errorf("returnURL(%q) = %q, want the site root", requested, got)
		}
	}
}

func TestReturnURLKeepsAnOwnSitePath(t *testing.T) {
	server := &Server{cfg: &config.Config{BaseURL: "https://cabinet.example.com"}}

	if got := server.returnURL("/payments/done"); got != "https://cabinet.example.com/payments/done" {
		t.Errorf("got %q", got)
	}
}

func TestTagNormalisation(t *testing.T) {
	// All three of these are what people actually have in their clipboard.
	cases := map[string]string{
		"@nickname":                 "nickname",
		"nickname":                  "nickname",
		"t.me/nickname":             "nickname",
		"https://t.me/nickname":     "nickname",
		"https://t.me/nickname?x=1": "nickname",
		"  @nickname  ":             "nickname",
		"":                          "",
	}
	for raw, want := range cases {
		if got := normalizeTag(raw); got != want {
			t.Errorf("normalizeTag(%q) = %q, want %q", raw, got, want)
		}
	}
}

func TestAReferrerCanBeNamedByTagOrByAddress(t *testing.T) {
	// Only a tag used to be accepted, which quietly excluded every referrer who
	// joined through the website: they have no Telegram tag, so nobody could
	// name them and they could never be credited.
	cases := map[string]string{
		"@nickname":             "nickname",
		"https://t.me/nickname": "nickname",
		"mail@example.com":      "mail@example.com",
		"  Mail@Example.COM  ":  "mail@example.com",
		// A leading @ before an address is habit, not part of it.
		"@mail@example.com": "mail@example.com",
		"":                  "",
	}
	for raw, want := range cases {
		if got := normalizeReferrerHandle(raw); got != want {
			t.Errorf("normalizeReferrerHandle(%q) = %q, want %q", raw, got, want)
		}
	}
}

func TestAnAddressIsNotPutThroughTheTagCleanup(t *testing.T) {
	// normalizeTag truncates at the first "/", "?" or "#". A plus-addressed
	// mailbox survives that, but the moment one does not, the customer is told
	// their referrer does not exist and has no way to tell why.
	const addr = "first.last+kaira@example.co.uk"
	if got := normalizeReferrerHandle(addr); got != addr {
		t.Errorf("normalizeReferrerHandle(%q) = %q, want it unchanged", addr, got)
	}
}

func TestSessionCookieIsHostPrefixed(t *testing.T) {
	// __Host- makes the browser refuse the cookie unless it is Secure, path=/
	// and has no Domain -- which stops a compromised subdomain from setting a
	// session cookie for us.
	if SessionCookie != "__Host-session" {
		t.Errorf("session cookie is %q", SessionCookie)
	}
}
