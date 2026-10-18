package main

import (
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"strings"
	"testing"
	"time"
)

func TestTheSmokeTestPassesOnlyWhenTheButtonReachesTheApp(t *testing.T) {
	for _, c := range []struct {
		name   string
		body   string
		failed bool
	}{
		{"the link arrives", `{"link":"` + smokeLink + `"}`, false},
		{"the body is lost on the way", ``, true},
	} {
		t.Run(c.name, func(t *testing.T) {
			marker := filepath.Join(t.TempDir(), "smoke")
			t.Setenv("VPNCHECK_SMOKE", marker)
			t.Setenv("VPNCHECK_SMOKE_HOLD", "1ms")
			s := newSmokeTest()
			s.buttonWait, s.settle = 50*time.Millisecond, 0
			page := s.watch(http.NotFoundHandler())
			page.ServeHTTP(httptest.NewRecorder(), httptest.NewRequest("GET", "/api/state", nil))
			quit := false
			s.drive(func(js string) {
				if !strings.Contains(js, smokeLink) {
					t.Errorf("script %q", js)
				}
				page.ServeHTTP(httptest.NewRecorder(), httptest.NewRequest("POST", "/api/check", strings.NewReader(c.body)))
			}, func() { quit = true })
			verdict, _ := os.ReadFile(marker)
			if s.failed != c.failed || !quit || (string(verdict) == "ok\n") == c.failed {
				t.Errorf("failed %v, quit %v, verdict %q", s.failed, quit, verdict)
			}
		})
	}
}
