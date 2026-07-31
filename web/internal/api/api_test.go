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

func TestSessionCookieIsHostPrefixed(t *testing.T) {
	// __Host- makes the browser refuse the cookie unless it is Secure, path=/
	// and has no Domain -- which stops a compromised subdomain from setting a
	// session cookie for us.
	if SessionCookie != "__Host-session" {
		t.Errorf("session cookie is %q", SessionCookie)
	}
}
