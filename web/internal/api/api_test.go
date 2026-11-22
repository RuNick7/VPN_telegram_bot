package api

import (
	"encoding/json"
	"errors"
	"net/http"
	"net/http/httptest"
	"net/netip"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/RuNick7/VPN_telegram_bot/web/internal/config"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/geoip"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/panel"
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

func TestNodeHealthIsSummedPerLocation(t *testing.T) {
	nodes := []panel.Node{
		{CountryCode: "FI", IsConnected: true},
		{CountryCode: "fi", IsConnected: true},
		{CountryCode: "DE", IsConnected: true},
		{CountryCode: "DE", IsConnected: false},
		{CountryCode: "NL", IsConnected: false},
		{CountryCode: "FR", IsConnected: true, IsDisabled: true}, // switched off on purpose
		{CountryCode: "RU", IsConnected: true},                   // not a location on the map
	}
	got := summarizeNodes(nodes)
	want := []locationStatus{
		{ID: "fi", State: "ok", Online: 2, Total: 2},
		{ID: "de", State: "partial", Online: 1, Total: 2},
		{ID: "nl", State: "down", Online: 0, Total: 1},
	}
	if len(got) != len(want) {
		t.Fatalf("got %d locations %+v, want %d", len(got), got, len(want))
	}
	for i := range want {
		if got[i] != want[i] {
			t.Errorf("location %d: got %+v, want %+v", i, got[i], want[i])
		}
	}
}

func TestServerStatusAsksThePanelSparingly(t *testing.T) {
	var cache statusCache
	calls := 0
	panelErr := errors.New("panel down")
	up := func() ([]panel.Node, error) {
		calls++
		return []panel.Node{{CountryCode: "FI", IsConnected: true}}, nil
	}
	down := func() ([]panel.Node, error) {
		calls++
		return nil, panelErr
	}
	start := time.Unix(1_800_000_000, 0)

	// With nothing cached, a failing panel is an error -- once. Visitors in the
	// next few seconds get the same answer without waiting on it again.
	if _, _, err := cache.get(start, down); !errors.Is(err, panelErr) {
		t.Fatalf("first failure: err %v", err)
	}
	if _, _, err := cache.get(start.Add(5*time.Second), down); !errors.Is(err, panelErr) || calls != 1 {
		t.Fatalf("within the retry window: err %v after %d calls, want the remembered error after 1", err, calls)
	}

	// Recovery is noticed once the window passes, and then cached a minute.
	at := start.Add(statusRetry)
	if got, _, err := cache.get(at, up); err != nil || len(got) != 1 || calls != 2 {
		t.Fatalf("after the window: %+v, %v after %d calls", got, err, calls)
	}
	if _, _, _ = cache.get(at.Add(30*time.Second), up); calls != 2 {
		t.Fatalf("a fresh answer was fetched again: %d calls", calls)
	}

	// A later failure keeps showing the last good answer, still at most once
	// per window, until that answer is too old to stand for the present.
	later := at.Add(statusFresh)
	if got, checked, err := cache.get(later, down); err != nil || len(got) != 1 || !checked.Equal(at) {
		t.Fatalf("stale answer: %+v checked %v, err %v", got, checked, err)
	}
	if _, _, _ = cache.get(later.Add(time.Second), down); calls != 3 {
		t.Fatalf("retried inside the window: %d calls", calls)
	}
	if _, _, err := cache.get(at.Add(statusStale), down); !errors.Is(err, panelErr) {
		t.Fatalf("an answer older than statusStale was still served: err %v", err)
	}
}
