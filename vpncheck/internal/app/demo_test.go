package app

import (
	"fmt"
	"net"
	"net/http"
	"os"
	"testing"
	"time"
)

// TestDemo serves the app on a fixed address with a made-up subscription of
// working and dead servers, for looking at the page and taking screenshots:
//
//	VPNCHECK_DEMO=127.0.0.1:8765 go test ./internal/app -run TestDemo -v -timeout 1h
//
// then open http://127.0.0.1:8765/#k=demo. VPNCHECK_DEMO_SITE names a
// website to talk to. Server names like de1.kaira.test
// are used where they resolve to this machine (an /etc/hosts line), plain
// 127.0.0.1 otherwise.
func TestDemo(t *testing.T) {
	addr := os.Getenv("VPNCHECK_DEMO")
	if addr == "" {
		t.Skip("VPNCHECK_DEMO is not set")
	}
	web := internet(t)
	host := func(name string) string {
		if ips, err := net.LookupHost(name); err == nil && len(ips) > 0 && net.ParseIP(ips[0]).IsLoopback() {
			return name
		}
		return "127.0.0.1"
	}
	working := func(tag, name string) map[string]any {
		out := vlessOutbound(tag, vlessNode(t))
		out["settings"].(map[string]any)["vnext"].([]any)[0].(map[string]any)["address"] = host(name)
		return out
	}
	dead := func(tag, name string) map[string]any {
		out := vlessOutbound(tag, freePort(t))
		out["settings"].(map[string]any)["vnext"].([]any)[0].(map[string]any)["address"] = host(name)
		return out
	}
	de1, de2 := working("de1", "de1.kaira.test"), working("de2", "de2.kaira.test")
	nl1, nl2 := working("nl1", "nl1.kaira.test"), dead("nl2", "nl2.kaira.test")
	fl1, fl2 := dead("fl1", "fl1.kaira.test"), dead("fl2", "fl2.kaira.test")
	us1, ru1 := working("us1", "us1.kaira.test"), working("ru1", "ru1.kaira.test")
	order := []string{"⚡️ Авто", "🇩🇪 Германия", "🇳🇱 Нидерланды", "🇫🇮 Финляндия", "🇺🇸 США", "🇷🇺 Россия · YouTube без рекламы"}
	p := newPanel(t, map[string][]map[string]any{
		order[0]: {de1, de2, nl1, nl2, fl1, fl2, us1},
		order[1]: {de1, de2},
		order[2]: {nl1, nl2},
		order[3]: {fl1, fl2},
		order[4]: {us1},
		order[5]: {ru1},
	}, order)
	p.headers["subscription-userinfo"] = fmt.Sprintf("upload=%d; download=%d; total=0; expire=%d", 2<<30, 41<<30, time.Now().Add(26*24*time.Hour).Unix())

	h := newHarness(t, web.URL)
	h.app.token = "demo"
	// A website to ask for the status and send the report to, when there is
	// one running (web/, with a panel that knows this link).
	h.app.cfg.Site = os.Getenv("VPNCHECK_DEMO_SITE")
	h.app.cfg.Options.Resolvers = nil
	h.app.cfg.Options.Parallel = 2
	listener, err := net.Listen("tcp", addr)
	if err != nil {
		t.Fatal(err)
	}
	go http.Serve(listener, h.app.Handler())
	fmt.Printf("page: http://%s/#k=demo\nlink: %s\n", addr, p.link())
	wait, _ := time.ParseDuration(os.Getenv("VPNCHECK_DEMO_FOR"))
	if wait == 0 {
		wait = 30 * time.Minute
	}
	time.Sleep(wait)
}
