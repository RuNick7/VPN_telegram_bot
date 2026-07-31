package api

import (
	"errors"
	"net/http"

	"github.com/RuNick7/VPN_telegram_bot/web/internal/auth"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/store"
)

type magicLinkRequest struct {
	Email string `json:"email"`
}

// handleRequestMagicLink emails a sign-in link.
//
// The response is identical whether or not the address has an account, and
// identical whether or not it was rate limited into doing nothing. Anything
// else turns this endpoint into a way to ask "does this person use the
// service?", which for a VPN is a question worth not answering.
func (s *Server) handleRequestMagicLink(w http.ResponseWriter, r *http.Request) {
	var body magicLinkRequest
	if err := decodeJSON(r, &body); err != nil {
		writeError(w, http.StatusBadRequest, "bad_request", "Некорректный запрос.")
		return
	}

	err := s.auth.RequestMagicLink(r.Context(), body.Email, clientIP(r))
	switch {
	case err == nil, errors.Is(err, auth.ErrRateLimited):
		// Deliberately the same answer. A rate-limited caller learns nothing.
	case errors.Is(err, auth.ErrInvalidEmail):
		writeError(w, http.StatusBadRequest, "invalid_email", "Проверьте адрес почты.")
		return
	default:
		// A send failure is ours, not the caller's, and they cannot act on it.
		s.log.Error("magic link", "err", err)
		writeError(w, http.StatusBadGateway, "mail_failed", "Не удалось отправить письмо. Попробуйте позже.")
		return
	}

	writeJSON(w, http.StatusOK, map[string]string{
		"status": "sent",
		"detail": "Если аккаунт с этим адресом существует, письмо со ссылкой уже отправлено.",
	})
}

type verifyRequest struct {
	Token string `json:"token"`
}

func (s *Server) handleVerifyMagicLink(w http.ResponseWriter, r *http.Request) {
	var body verifyRequest
	if err := decodeJSON(r, &body); err != nil || body.Token == "" {
		writeError(w, http.StatusBadRequest, "bad_request", "Некорректный запрос.")
		return
	}

	session, user, err := s.auth.RedeemMagicLink(r.Context(), body.Token, clientIP(r), r.UserAgent())
	switch {
	case errors.Is(err, auth.ErrBadToken):
		writeError(w, http.StatusUnauthorized, "bad_token",
			"Ссылка недействительна, истекла или уже была использована.")
		return
	case errors.Is(err, auth.ErrRateLimited):
		writeError(w, http.StatusTooManyRequests, "rate_limited", "Слишком много попыток. Подождите немного.")
		return
	case err != nil:
		s.fail(w, r, err)
		return
	}

	s.setSessionCookie(w, session)
	writeJSON(w, http.StatusOK, meResponse(user))
}

func (s *Server) handleTelegramLogin(w http.ResponseWriter, r *http.Request) {
	if !s.cfg.TelegramLoginEnabled() {
		writeError(w, http.StatusNotImplemented, "not_configured", "Вход через Telegram не настроен.")
		return
	}

	var payload auth.TelegramAuth
	if err := decodeJSON(r, &payload); err != nil {
		writeError(w, http.StatusBadRequest, "bad_request", "Некорректный запрос.")
		return
	}

	session, user, err := s.auth.LoginWithTelegram(r.Context(), payload, clientIP(r), r.UserAgent())
	switch {
	case errors.Is(err, auth.ErrTelegramSignature), errors.Is(err, auth.ErrTelegramStale):
		writeError(w, http.StatusUnauthorized, "bad_signature", "Данные Telegram не прошли проверку.")
		return
	case errors.Is(err, store.ErrNotFound):
		// No account for this Telegram user. Creating one here would mean
		// creating a panel profile and a trial from an unauthenticated
		// endpoint; the bot's /start owns that.
		writeError(w, http.StatusNotFound, "no_account",
			"Аккаунт не найден. Откройте бота и нажмите /start, затем войдите снова.")
		return
	case err != nil:
		s.fail(w, r, err)
		return
	}

	s.setSessionCookie(w, session)
	writeJSON(w, http.StatusOK, meResponse(user))
}

func (s *Server) handleLogout(w http.ResponseWriter, r *http.Request) {
	if cookie, err := r.Cookie(SessionCookie); err == nil && cookie.Value != "" {
		if err := s.auth.EndSession(r.Context(), cookie.Value); err != nil {
			s.log.Error("logout", "err", err)
		}
	}
	// Cleared unconditionally: a session row that could not be deleted must
	// still stop being presented by this browser.
	s.clearSessionCookie(w)
	writeJSON(w, http.StatusOK, map[string]string{"status": "logged_out"})
}
