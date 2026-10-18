package main

import (
	"bytes"
	"fmt"
	"io"
	"net/http"
	"os"
	"time"
)

// smokeTest is the release check of a built app on a real system (CI): the
// window opens, the page runs under its CSP, and a button's request reaches
// the app with its body. VPNCHECK_SMOKE names a file the verdict is written
// to; the window then stays a few seconds for a screenshot and closes.
type smokeTest struct {
	marker string
	state  chan struct{}
	check  chan struct{}
	failed bool
	// How long the page may take to load, the request to arrive, and the
	// answer to be drawn.
	pageWait, buttonWait, settle time.Duration
}

// A link the check turns away without going anywhere.
const smokeLink = "https://example.invalid/vpncheck-smoke-0123456789"

func newSmokeTest() *smokeTest {
	marker := os.Getenv("VPNCHECK_SMOKE")
	if marker == "" {
		return nil
	}
	return &smokeTest{
		marker: marker, state: make(chan struct{}, 1), check: make(chan struct{}, 1),
		pageWait: time.Minute, buttonWait: 30 * time.Second, settle: 2 * time.Second,
	}
}

func (s *smokeTest) watch(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch {
		case r.Method == http.MethodGet && r.URL.Path == "/api/state":
			notify(s.state)
		case r.Method == http.MethodPost && r.URL.Path == "/api/check":
			body, _ := io.ReadAll(io.LimitReader(r.Body, 1<<16))
			r.Body = io.NopCloser(bytes.NewReader(body))
			if bytes.Contains(body, []byte(smokeLink)) {
				notify(s.check)
			}
		}
		next.ServeHTTP(w, r)
	})
}

func notify(ch chan struct{}) {
	select {
	case ch <- struct{}{}:
	default:
	}
}

// drive works the page once it is loaded: types the link, presses
// «Проверить», and waits for the request. exec runs a script in the page,
// quit closes the window.
func (s *smokeTest) drive(exec func(string), quit func()) {
	verdict := "ok"
	select {
	case <-s.state:
		exec(fmt.Sprintf(`document.getElementById("link").value = %q; document.getElementById("start").click();`, smokeLink))
		select {
		case <-s.check:
		case <-time.After(s.buttonWait):
			verdict = "fail: «Проверить» did not reach the app"
		}
	case <-time.After(s.pageWait):
		verdict = "fail: the page never asked the app for its state"
	}
	// The page draws the answer before anyone looks.
	time.Sleep(s.settle)
	s.failed = verdict != "ok"
	_ = os.WriteFile(s.marker, []byte(verdict+"\n"), 0o644)
	hold, _ := time.ParseDuration(os.Getenv("VPNCHECK_SMOKE_HOLD"))
	if hold == 0 {
		hold = 5 * time.Second
	}
	time.Sleep(hold)
	quit()
}
