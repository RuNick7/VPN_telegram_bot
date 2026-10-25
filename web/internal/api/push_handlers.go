package api

import (
	"net/http"
	"sync"
	"time"

	"github.com/RuNick7/VPN_telegram_bot/web/internal/push"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/store"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/webpush"
)

// Web Push from the customer's side: register this browser, say what to hear
// about, and send oneself a test. What is sent and when is internal/push.

// EnablePush switches the endpoints on. Called once at start-up, before
// serving, when a VAPID key is configured.
func (s *Server) EnablePush(p *push.Service) {
	s.push = p
	s.pushTests = &testLimiter{every: 30 * time.Second, last: map[string]time.Time{}}
}

func (s *Server) pushOnly(next handlerWithUser) handlerWithUser {
	return func(w http.ResponseWriter, r *http.Request, user *store.User) {
		if s.push == nil {
			writeError(w, http.StatusNotFound, "not_found", "Уведомления недоступны.")
			return
		}
		next(w, r, user)
	}
}

func (s *Server) handlePushStatus(w http.ResponseWriter, r *http.Request, user *store.User) {
	if s.push == nil {
		writeJSON(w, http.StatusOK, map[string]any{"push_enabled": false})
		return
	}
	prefs, err := s.store.PushPreferences(r.Context(), user.ID)
	if err != nil {
		s.fail(w, r, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{
		"push_enabled": true,
		"public_key":   s.push.PublicKey,
		"preferences":  prefs,
	})
}

type pushSubscriptionBody struct {
	Endpoint string `json:"endpoint"`
	P256dh   string `json:"p256dh"`
	Auth     string `json:"auth"`
}

func (s *Server) handleSavePushSubscription(w http.ResponseWriter, r *http.Request, user *store.User) {
	var body pushSubscriptionBody
	if err := decodeJSON(r, &body); err != nil {
		writeError(w, http.StatusBadRequest, "bad_request", "Некорректный запрос.")
		return
	}
	// The endpoint is a URL this server will POST to; anything but a known
	// push service is refused here, and again before every send.
	if !webpush.ValidEndpoint(body.Endpoint) || len(body.P256dh) > 200 || len(body.Auth) > 64 ||
		body.P256dh == "" || body.Auth == "" {
		writeError(w, http.StatusBadRequest, "bad_subscription", "Браузер вернул неподдерживаемую подписку.")
		return
	}
	if err := s.store.SavePushSubscription(r.Context(), user.ID, body.Endpoint, body.P256dh, body.Auth); err != nil {
		s.fail(w, r, err)
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

func (s *Server) handleDeletePushSubscription(w http.ResponseWriter, r *http.Request, user *store.User) {
	var body struct {
		Endpoint string `json:"endpoint"`
	}
	if err := decodeJSON(r, &body); err != nil || body.Endpoint == "" {
		writeError(w, http.StatusBadRequest, "bad_request", "Некорректный запрос.")
		return
	}
	if err := s.store.DeletePushSubscription(r.Context(), user.ID, body.Endpoint); err != nil {
		s.fail(w, r, err)
		return
	}
	w.WriteHeader(http.StatusNoContent)
}

func (s *Server) handleSetPushPreferences(w http.ResponseWriter, r *http.Request, user *store.User) {
	var prefs store.PushPreferences
	if err := decodeJSON(r, &prefs); err != nil {
		writeError(w, http.StatusBadRequest, "bad_request", "Некорректный запрос.")
		return
	}
	if err := s.store.SetPushPreferences(r.Context(), user.ID, prefs); err != nil {
		s.fail(w, r, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"preferences": prefs})
}

// handleTestPush sends the caller a notification on every browser they have,
// which is how a customer -- or whoever deploys this -- finds out whether
// notifications actually arrive.
func (s *Server) handleTestPush(w http.ResponseWriter, r *http.Request, user *store.User) {
	if !s.pushTests.allow(user.ID) {
		writeError(w, http.StatusTooManyRequests, "rate_limited", "Подождите полминуты перед следующей проверкой.")
		return
	}
	delivered, err := s.push.SendToUser(r.Context(), user.ID, webpush.Message{
		Title: "KairaVPN",
		Body:  "Уведомления работают.",
		URL:   "/app/profile",
		Tag:   "test",
	}, 10*time.Minute)
	if delivered == 0 {
		if err != nil {
			s.log.Warn("test push failed", "err", err)
		}
		writeError(w, http.StatusBadGateway, "push_failed",
			"Не удалось доставить уведомление. Включите уведомления на этом устройстве заново.")
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"delivered": delivered})
}

// testLimiter allows one call per key per interval. In memory: it guards a
// button, not anything that matters across a restart.
type testLimiter struct {
	mu    sync.Mutex
	every time.Duration
	last  map[string]time.Time
}

func (l *testLimiter) allow(key string) bool {
	l.mu.Lock()
	defer l.mu.Unlock()
	now := time.Now()
	if last, ok := l.last[key]; ok && now.Sub(last) < l.every {
		return false
	}
	for k, t := range l.last {
		if now.Sub(t) >= l.every {
			delete(l.last, k)
		}
	}
	l.last[key] = now
	return true
}
