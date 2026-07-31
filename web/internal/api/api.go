// Package api is the website's JSON HTTP surface.
//
// It serves JSON only. The frontend is static files served by whatever sits in
// front of this (nginx, or `go run` during development) and talks to these
// endpoints; nothing here renders HTML, so a template bug cannot become an
// injection bug.
package api

import (
	"encoding/json"
	"errors"
	"log/slog"
	"net"
	"net/http"
	"strings"
	"time"

	"github.com/RuNick7/VPN_telegram_bot/web/internal/account"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/auth"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/config"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/store"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/yookassa"
)

// SessionCookie is the browser-side name of the session token.
//
// `__Host-` is not a decoration: it makes the browser refuse the cookie unless
// it is Secure, path=/, and has no Domain attribute, which stops a subdomain
// -- including one an attacker gets control of -- from setting a session
// cookie for us.
const SessionCookie = "__Host-session"

type Server struct {
	cfg      *config.Config
	store    *store.Store
	auth     *auth.Service
	account  *account.Service
	payments *yookassa.Client
	log      *slog.Logger
}

func NewServer(
	cfg *config.Config,
	st *store.Store,
	authSvc *auth.Service,
	accountSvc *account.Service,
	payments *yookassa.Client,
	log *slog.Logger,
) *Server {
	return &Server{cfg: cfg, store: st, auth: authSvc, account: accountSvc, payments: payments, log: log}
}

func (s *Server) Routes() http.Handler {
	mux := http.NewServeMux()

	mux.HandleFunc("GET /api/health", s.handleHealth)
	mux.HandleFunc("GET /api/config", s.handleClientConfig)

	// Auth. Unauthenticated by definition.
	mux.HandleFunc("POST /api/auth/magic-link", s.handleRequestMagicLink)
	mux.HandleFunc("POST /api/auth/verify", s.handleVerifyMagicLink)
	mux.HandleFunc("POST /api/auth/telegram", s.handleTelegramLogin)
	mux.HandleFunc("POST /api/auth/logout", s.handleLogout)

	// Everything below requires a session.
	mux.Handle("GET /api/me", s.authenticated(s.handleMe))
	mux.Handle("PATCH /api/me/email", s.authenticated(s.handleUpdateEmail))

	mux.Handle("GET /api/subscription", s.authenticated(s.handleSubscription))
	mux.Handle("POST /api/subscription/reset-link", s.authenticated(s.handleResetLink))

	mux.Handle("GET /api/devices", s.authenticated(s.handleListDevices))
	mux.Handle("DELETE /api/devices/{id}", s.authenticated(s.handleDeleteDevice))

	mux.Handle("GET /api/traffic", s.authenticated(s.handleTraffic))
	mux.Handle("GET /api/plans", s.authenticated(s.handlePlans))

	mux.Handle("POST /api/payments/subscription", s.authenticated(s.handleBuySubscription))
	mux.Handle("POST /api/payments/traffic", s.authenticated(s.handleBuyTraffic))
	mux.Handle("POST /api/payments/gift", s.authenticated(s.handleBuyGift))
	mux.Handle("GET /api/payments/{id}", s.authenticated(s.handlePaymentStatus))

	mux.Handle("GET /api/referrals", s.authenticated(s.handleReferrals))
	mux.Handle("PUT /api/referrals/referrer", s.authenticated(s.handleSetReferrer))

	mux.Handle("POST /api/promo/redeem", s.authenticated(s.handleRedeemPromo))

	mux.Handle("GET /api/link/telegram", s.authenticated(s.handleLinkStatus))
	mux.Handle("POST /api/link/telegram", s.authenticated(s.handleCreateTelegramLink))

	return s.withRecovery(s.withSecurityHeaders(mux))
}

// -- middleware -------------------------------------------------------------

type handlerWithUser func(w http.ResponseWriter, r *http.Request, user *store.User)

// authenticated rejects anything without a valid session before the handler
// runs, so no handler below has to remember to check.
func (s *Server) authenticated(next handlerWithUser) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		cookie, err := r.Cookie(SessionCookie)
		if err != nil || cookie.Value == "" {
			writeError(w, http.StatusUnauthorized, "not_authenticated", "Требуется вход.")
			return
		}
		user, err := s.auth.UserForSession(r.Context(), cookie.Value)
		if errors.Is(err, store.ErrNotFound) {
			// The cookie is dead; clear it so the browser stops sending it.
			s.clearSessionCookie(w)
			writeError(w, http.StatusUnauthorized, "session_expired", "Сессия истекла, войдите снова.")
			return
		}
		if err != nil {
			s.fail(w, r, err)
			return
		}
		next(w, r, user)
	})
}

func (s *Server) withSecurityHeaders(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.Header().Set("X-Content-Type-Options", "nosniff")
		w.Header().Set("Referrer-Policy", "same-origin")
		w.Header().Set("X-Frame-Options", "DENY")
		w.Header().Set("Cache-Control", "no-store")
		next.ServeHTTP(w, r)
	})
}

// withRecovery keeps one panicking request from taking the process with it.
func (s *Server) withRecovery(next http.Handler) http.Handler {
	return http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		defer func() {
			if recovered := recover(); recovered != nil {
				s.log.Error("panic serving request", "path", r.URL.Path, "panic", recovered)
				writeError(w, http.StatusInternalServerError, "internal", "Внутренняя ошибка.")
			}
		}()
		next.ServeHTTP(w, r)
	})
}

// -- responses --------------------------------------------------------------

func writeJSON(w http.ResponseWriter, status int, payload any) {
	w.Header().Set("Content-Type", "application/json; charset=utf-8")
	w.WriteHeader(status)
	if payload != nil {
		_ = json.NewEncoder(w).Encode(payload)
	}
}

type errorBody struct {
	Error   string `json:"error"`
	Message string `json:"message"`
}

func writeError(w http.ResponseWriter, status int, code, message string) {
	writeJSON(w, status, errorBody{Error: code, Message: message})
}

// fail logs the real cause and tells the client nothing about it.
//
// Panel errors and database errors carry hostnames, SQL and occasionally
// credentials; none of that belongs in a response body.
func (s *Server) fail(w http.ResponseWriter, r *http.Request, err error) {
	s.log.Error("request failed", "path", r.URL.Path, "err", err)
	writeError(w, http.StatusInternalServerError, "internal", "Что-то пошло не так, попробуйте позже.")
}

func decodeJSON(r *http.Request, target any) error {
	decoder := json.NewDecoder(http.MaxBytesReader(nil, r.Body, 64*1024))
	decoder.DisallowUnknownFields()
	return decoder.Decode(target)
}

// -- cookies ----------------------------------------------------------------

func (s *Server) setSessionCookie(w http.ResponseWriter, token string) {
	http.SetCookie(w, &http.Cookie{
		Name:     SessionCookie,
		Value:    token,
		Path:     "/",
		MaxAge:   int(s.auth.SessionTTL().Seconds()),
		HttpOnly: true, // unreadable from JavaScript, so an XSS cannot lift it
		Secure:   true,
		// Lax rather than Strict: the magic link arrives as a top-level
		// navigation from an email client, and Strict would drop the cookie on
		// exactly that first request.
		SameSite: http.SameSiteLaxMode,
	})
}

func (s *Server) clearSessionCookie(w http.ResponseWriter) {
	http.SetCookie(w, &http.Cookie{
		Name: SessionCookie, Value: "", Path: "/", MaxAge: -1,
		HttpOnly: true, Secure: true, SameSite: http.SameSiteLaxMode,
	})
}

// -- misc -------------------------------------------------------------------

func clientIP(r *http.Request) string {
	// X-Forwarded-For is only meaningful behind our own proxy, and is trusted
	// no further than rate-limit bucketing -- nothing authorises on it.
	if forwarded := r.Header.Get("X-Forwarded-For"); forwarded != "" {
		if first, _, ok := strings.Cut(forwarded, ","); ok {
			return strings.TrimSpace(first)
		}
		return strings.TrimSpace(forwarded)
	}
	host, _, err := net.SplitHostPort(r.RemoteAddr)
	if err != nil {
		return r.RemoteAddr
	}
	return host
}

func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	ctx, cancel := contextWithTimeout(r, 2*time.Second)
	defer cancel()
	if err := s.store.Pool().Ping(ctx); err != nil {
		writeError(w, http.StatusServiceUnavailable, "database", "Нет связи с базой данных.")
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"status": "ok"})
}

// handleClientConfig tells the frontend which login routes and features are
// available, so it can render the right buttons instead of guessing.
func (s *Server) handleClientConfig(w http.ResponseWriter, r *http.Request) {
	writeJSON(w, http.StatusOK, map[string]any{
		"telegram_login":   s.cfg.TelegramLoginEnabled(),
		"telegram_bot":     s.cfg.TelegramBotUsername,
		"payments_enabled": s.cfg.PaymentsEnabled(),
		"traffic_enabled":  s.cfg.LTEEnabled,
		"trial_days":       s.cfg.WebTrialDays,
	})
}
