package api

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"net/netip"
	"os"
	"strings"
	"testing"

	"github.com/RuNick7/VPN_telegram_bot/web/internal/config"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/geoip"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/pricing"
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

func TestReferralLadderFollowsThePriceTable(t *testing.T) {
	ladder := referralLadder()
	if len(ladder) != pricing.MaxTier+1 {
		t.Fatalf("ladder has %d steps, want %d", len(ladder), pricing.MaxTier+1)
	}
	for invited, price := range ladder {
		want, _ := pricing.SubscriptionPrice(1, invited)
		if price != want {
			t.Errorf("step %d is %d ₽, the table says %d ₽", invited, price, want)
		}
		if invited > 0 && price > ladder[invited-1] {
			t.Errorf("inviting a friend raises the price at step %d", invited)
		}
	}
	if ladder[len(ladder)-1] != referralBestPrice() {
		t.Errorf("the last step %d ₽ is not the best price %d ₽", ladder[len(ladder)-1], referralBestPrice())
	}
}

func TestWhereAmIWithoutADatabaseIsUnknown(t *testing.T) {
	s := &Server{}
	rec := httptest.NewRecorder()
	req := httptest.NewRequest(http.MethodGet, "/api/whereami", nil)
	req.RemoteAddr = "77.88.8.8:5000"
	s.handleWhereAmI(rec, req)
	if rec.Code != http.StatusNoContent {
		t.Errorf("status %d, want 204", rec.Code)
	}
	if got := rec.Header().Get("Cache-Control"); !strings.Contains(got, "no-store") {
		t.Errorf("Cache-Control %q: a city answer must not be cached for the next visitor", got)
	}
}

func TestOnlyPublicAddressesAreLookedUp(t *testing.T) {
	for addr, want := range map[string]bool{
		"77.88.8.8":          true,
		"2a02:6b8::feed:0ff": true,
		"::ffff:77.88.8.8":   true,
		"127.0.0.1":          false, // everybody, behind a proxy that hides the address
		"10.1.2.3":           false,
		"192.168.0.10":       false,
		"::1":                false,
		"fe80::1":            false,
	} {
		if got := publicAddress(netip.MustParseAddr(addr)); got != want {
			t.Errorf("publicAddress(%s) = %v, want %v", addr, got, want)
		}
	}
}

// End to end against a real city database when GEOIP_TEST_DB names one:
// the address arrives the way it does behind the proxy, in X-Forwarded-For.
func TestWhereAmIWithARealDatabase(t *testing.T) {
	path := os.Getenv("GEOIP_TEST_DB")
	if path == "" {
		t.Skip("GEOIP_TEST_DB not set")
	}
	db, err := geoip.Open(path)
	if err != nil {
		t.Fatal(err)
	}
	defer db.Close()
	s := &Server{}
	s.EnableGeo(db)

	req := httptest.NewRequest(http.MethodGet, "/api/whereami", nil)
	req.RemoteAddr = "127.0.0.1:40000"
	req.Header.Set("X-Forwarded-For", "46.61.0.1")
	rec := httptest.NewRecorder()
	s.handleWhereAmI(rec, req)
	if rec.Code != http.StatusOK {
		t.Fatalf("status %d", rec.Code)
	}
	var place geoip.Place
	if err := json.Unmarshal(rec.Body.Bytes(), &place); err != nil {
		t.Fatal(err)
	}
	if place.Country != "RU" || place.Lat == 0 || place.Lon == 0 {
		t.Errorf("got %+v", place)
	}
	if strings.Contains(rec.Body.String(), "46.61.0.1") {
		t.Error("the answer echoes the address back")
	}

	// Behind a proxy that hides addresses everyone is loopback: unknown.
	req = httptest.NewRequest(http.MethodGet, "/api/whereami", nil)
	req.RemoteAddr = "127.0.0.1:40000"
	rec = httptest.NewRecorder()
	s.handleWhereAmI(rec, req)
	if rec.Code != http.StatusNoContent {
		t.Errorf("loopback: status %d, want 204", rec.Code)
	}
}
