package api

import (
	"bytes"
	"encoding/json"
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/RuNick7/VPN_telegram_bot/web/internal/push"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/webpush"
)

func (e *supportEnv) enablePush() {
	e.t.Helper()
	public, private, _ := webpush.GenerateKeys()
	keys, err := webpush.ParseKeys(public, private)
	if err != nil {
		e.t.Fatal(err)
	}
	e.server.EnablePush(push.New(e.store, keys, "mailto:ops@example.com", slog.New(slog.NewTextHandler(io.Discard, nil))))
}

func (e *supportEnv) sendJSON(method, target, token string, body any) *httptest.ResponseRecorder {
	e.t.Helper()
	raw, _ := json.Marshal(body)
	r := httptest.NewRequest(method, target, bytes.NewReader(raw))
	r.Header.Set("Content-Type", "application/json")
	r.AddCookie(&http.Cookie{Name: SessionCookie, Value: token})
	recorder := httptest.NewRecorder()
	e.handler.ServeHTTP(recorder, r)
	return recorder
}

func TestPushIsReportedOffWhenNotConfigured(t *testing.T) {
	e := newSupportEnv(t)
	_, token := e.customer()
	response := e.get("/api/push", token)
	if response.Code != http.StatusOK || !bytes.Contains(response.Body.Bytes(), []byte(`"push_enabled":false`)) {
		t.Errorf("%d %s", response.Code, response.Body)
	}
	if code := e.sendJSON(http.MethodPut, "/api/push/subscription", token, map[string]string{}).Code; code != http.StatusNotFound {
		t.Errorf("subscribing with push off: %d", code)
	}
}

func TestPushStatusCarriesTheKeyAndTheDefaults(t *testing.T) {
	e := newSupportEnv(t)
	e.enablePush()
	_, token := e.customer()
	var status struct {
		Enabled   bool            `json:"push_enabled"`
		PublicKey string          `json:"public_key"`
		Prefs     map[string]bool `json:"preferences"`
	}
	response := e.get("/api/push", token)
	_ = json.Unmarshal(response.Body.Bytes(), &status)
	if !status.Enabled || status.PublicKey == "" {
		t.Fatalf("%s", response.Body)
	}
	want := map[string]bool{"expiry": true, "support": true, "payment": false}
	for k, v := range want {
		if status.Prefs[k] != v {
			t.Errorf("default %s = %v", k, status.Prefs[k])
		}
	}

	e.sendJSON(http.MethodPut, "/api/push/preferences", token, map[string]bool{"expiry": false, "support": true, "payment": true})
	_ = json.Unmarshal(e.get("/api/push", token).Body.Bytes(), &status)
	if status.Prefs["expiry"] || !status.Prefs["payment"] {
		t.Errorf("after saving: %+v", status.Prefs)
	}
}

func TestOnlyPushServiceEndpointsAreAccepted(t *testing.T) {
	e := newSupportEnv(t)
	e.enablePush()
	userID, token := e.customer()

	for _, endpoint := range []string{"https://postgres:5432/", "http://fcm.googleapis.com/x", "https://example.com/push"} {
		code := e.sendJSON(http.MethodPut, "/api/push/subscription", token,
			map[string]string{"endpoint": endpoint, "p256dh": "k", "auth": "a"}).Code
		if code != http.StatusBadRequest {
			t.Errorf("%s: %d", endpoint, code)
		}
	}

	endpoint := "https://fcm.googleapis.com/fcm/send/" + userID
	if code := e.sendJSON(http.MethodPut, "/api/push/subscription", token,
		map[string]string{"endpoint": endpoint, "p256dh": "k", "auth": "a"}).Code; code != http.StatusNoContent {
		t.Fatalf("valid subscription: %d", code)
	}
	if subs, _ := e.store.PushSubscriptions(t.Context(), userID); len(subs) != 1 {
		t.Fatalf("stored %d", len(subs))
	}

	// Someone else cannot remove it by naming it.
	_, other := e.customer()
	e.sendJSON(http.MethodDelete, "/api/push/subscription", other, map[string]string{"endpoint": endpoint})
	if subs, _ := e.store.PushSubscriptions(t.Context(), userID); len(subs) != 1 {
		t.Error("another account deleted this browser")
	}
	e.sendJSON(http.MethodDelete, "/api/push/subscription", token, map[string]string{"endpoint": endpoint})
	if subs, _ := e.store.PushSubscriptions(t.Context(), userID); len(subs) != 0 {
		t.Error("the owner could not remove it")
	}
}

func TestATestPushIsRateLimited(t *testing.T) {
	e := newSupportEnv(t)
	e.enablePush()
	_, token := e.customer()
	// No browsers: the first is refused as undeliverable, the second as too soon.
	if code := e.sendJSON(http.MethodPost, "/api/push/test", token, nil).Code; code != http.StatusBadGateway {
		t.Errorf("first: %d", code)
	}
	if code := e.sendJSON(http.MethodPost, "/api/push/test", token, nil).Code; code != http.StatusTooManyRequests {
		t.Errorf("second: %d", code)
	}
}
