package deeplink

import (
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

// The real shape, and the only one that matters: an app scheme whose payload is
// itself an https:// URL.
const realLink = "happ://add/https://sub.kairavpn.pro/2wvpucv-MMuRnqsp"

func TestAnAppLinkSurvivesByteForByte(t *testing.T) {
	// Round-tripping it through net/url collapses the `//` in the inner
	// https:// and the app then imports nothing, so the check has to be
	// equality with what came in -- not "parses to something equivalent".
	got, err := Target(realLink)
	if err != nil {
		t.Fatalf("Target(%q): %v", realLink, err)
	}
	if got != realLink {
		t.Errorf("got %q, want it unchanged", got)
	}
}

func TestTheSchemeIsMatchedWithoutRegardToCase(t *testing.T) {
	if _, err := Target("HAPP://add/https://sub.example.com/tok"); err != nil {
		t.Errorf("uppercase scheme refused: %v", err)
	}
}

// -- what makes this not an open redirector --------------------------------

func TestAWebAddressIsRefused(t *testing.T) {
	// The whole point. `/auto/?url=https://not-us.example` would be a phishing
	// link wearing our domain, and the domain is the part people are told to
	// check.
	for _, raw := range []string{
		"https://not-us.example/login",
		"http://not-us.example",
		"//not-us.example",
		"/app/profile",
	} {
		if _, err := Target(raw); err == nil {
			t.Errorf("Target(%q) was allowed", raw)
		}
	}
}

func TestAScriptURLIsRefused(t *testing.T) {
	for _, raw := range []string{"javascript:alert(1)", "data:text/html,<script>"} {
		if _, err := Target(raw); err == nil {
			t.Errorf("Target(%q) was allowed", raw)
		}
	}
}

func TestAnUnknownAppIsRefused(t *testing.T) {
	// Adding a client app means adding it here deliberately, rather than this
	// domain vouching for whatever scheme somebody puts in a link.
	if _, err := Target("v2raytun://import/https://sub.example.com/tok"); err == nil {
		t.Error("an unlisted scheme was allowed")
	}
}

func TestALineBreakCannotBecomeASecondHeader(t *testing.T) {
	if _, err := Target("happ://add/x\r\nSet-Cookie: a=b"); err == nil {
		t.Error("a control character was allowed into a header value")
	}
}

func TestNothingAtAllIsRefused(t *testing.T) {
	for _, raw := range []string{"", "   ", "happ:", "happ"} {
		if _, err := Target(raw); err == nil {
			t.Errorf("Target(%q) was allowed", raw)
		}
	}
}

// -- the handler -----------------------------------------------------------

func quietHandler() http.Handler {
	return Handler(slog.New(slog.NewTextHandler(io.Discard, nil)))
}

func get(t *testing.T, target string) *httptest.ResponseRecorder {
	t.Helper()
	recorder := httptest.NewRecorder()
	quietHandler().ServeHTTP(recorder, httptest.NewRequest(http.MethodGet, target, nil))
	return recorder
}

func TestTheRedirectPointsAtTheApp(t *testing.T) {
	recorder := get(t, "/auto?url="+strings.ReplaceAll(realLink, ":", "%3A"))

	if recorder.Code != http.StatusFound {
		t.Fatalf("status = %d, want 302", recorder.Code)
	}
	if location := recorder.Header().Get("Location"); location != realLink {
		t.Errorf("Location = %q, want %q", location, realLink)
	}
}

func TestAnUnencodedLinkWorksToo(t *testing.T) {
	// What somebody gets when they copy the URL out of the bot and edit it by
	// hand. `:` and `/` are legal in a query, so this has to keep working.
	recorder := get(t, "/auto/?url="+realLink)

	if recorder.Code != http.StatusFound {
		t.Fatalf("status = %d, want 302", recorder.Code)
	}
	if location := recorder.Header().Get("Location"); location != realLink {
		t.Errorf("Location = %q, want %q", location, realLink)
	}
}

func TestTheSubscriptionIsNotLeftInACache(t *testing.T) {
	// The query string carries the credential itself.
	recorder := get(t, "/auto?url="+realLink)

	if store := recorder.Header().Get("Cache-Control"); !strings.Contains(store, "no-store") {
		t.Errorf("Cache-Control = %q, want no-store", store)
	}
	if referrer := recorder.Header().Get("Referrer-Policy"); referrer != "no-referrer" {
		t.Errorf("Referrer-Policy = %q, want no-referrer", referrer)
	}
}

func TestARefusalSaysNothingBackToTheCaller(t *testing.T) {
	// The parameter is a credential on the ordinary path and attacker text on
	// this one. Echoing it would make the page a reflection surface and put the
	// other kind in a log.
	recorder := get(t, "/auto?url=https://not-us.example/phish")

	if recorder.Code != http.StatusBadRequest {
		t.Fatalf("status = %d, want 400", recorder.Code)
	}
	if strings.Contains(recorder.Body.String(), "not-us.example") {
		t.Errorf("the refused value was echoed back: %q", recorder.Body.String())
	}
	if recorder.Header().Get("Location") != "" {
		t.Error("a refused link still set Location")
	}
}

func TestARealServerPutsTheAppSchemeOnTheWire(t *testing.T) {
	// Everything above goes through httptest.NewRecorder, which is a map with
	// a Header() method -- it will happily "send" a header net/http would drop.
	// A scheme no browser-facing header normally carries is exactly the case
	// where that difference decides whether the feature works at all, so this
	// one goes over a socket.
	server := httptest.NewServer(quietHandler())
	defer server.Close()

	client := &http.Client{
		CheckRedirect: func(*http.Request, []*http.Request) error { return http.ErrUseLastResponse },
	}
	response, err := client.Get(server.URL + "/auto/?url=" + realLink)
	if err != nil {
		t.Fatalf("GET: %v", err)
	}
	defer response.Body.Close()

	if response.StatusCode != http.StatusFound {
		t.Fatalf("status = %d, want 302", response.StatusCode)
	}
	if location := response.Header.Get("Location"); location != realLink {
		t.Errorf("Location = %q, want %q", location, realLink)
	}
	body, _ := io.ReadAll(response.Body)
	if len(body) != 0 {
		t.Errorf("body = %q, want it empty", body)
	}
}

func TestOnlyReadsAreAnswered(t *testing.T) {
	recorder := httptest.NewRecorder()
	quietHandler().ServeHTTP(recorder, httptest.NewRequest(http.MethodPost, "/auto?url="+realLink, nil))

	if recorder.Code != http.StatusMethodNotAllowed {
		t.Errorf("status = %d, want 405", recorder.Code)
	}
}
