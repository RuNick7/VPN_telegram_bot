package api

import (
	"errors"
	"net/http"
	"strconv"
	"strings"

	"github.com/RuNick7/VPN_telegram_bot/web/internal/auth"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/store"
)

// handleTelegramCallback signs a visitor in from Telegram's login widget.
//
// This is the widget's *redirect* mode: Telegram sends the browser here with
// the signed payload in the query string. The alternative -- a JavaScript
// callback -- has the widget script evaluate an attribute of the page, which
// would mean allowing 'unsafe-eval' in the Content-Security-Policy of every
// page for the sake of one optional button. Nothing is trusted differently for
// arriving in a URL: the same HMAC check runs either way, and it is what
// decides whether a session is issued.
//
// Answering a GET with a session cookie is safe here for the same reason the
// magic link is: the payload is a one-time signed credential, not an action on
// an existing account, and it is Telegram that navigated the browser here.
func (s *Server) handleTelegramCallback(w http.ResponseWriter, r *http.Request) {
	if !s.cfg.TelegramLoginEnabled() {
		s.bounce(w, r, "not_configured")
		return
	}

	query := r.URL.Query()
	id, err := strconv.ParseInt(strings.TrimSpace(query.Get("id")), 10, 64)
	if err != nil {
		s.bounce(w, r, "bad_signature")
		return
	}
	authDate, err := strconv.ParseInt(strings.TrimSpace(query.Get("auth_date")), 10, 64)
	if err != nil {
		s.bounce(w, r, "bad_signature")
		return
	}

	payload := auth.TelegramAuth{
		ID:        id,
		FirstName: query.Get("first_name"),
		LastName:  query.Get("last_name"),
		Username:  query.Get("username"),
		PhotoURL:  query.Get("photo_url"),
		AuthDate:  authDate,
		Hash:      query.Get("hash"),
	}

	session, _, err := s.auth.LoginWithTelegram(r.Context(), payload, clientIP(r), r.UserAgent())
	switch {
	case errors.Is(err, auth.ErrTelegramSignature), errors.Is(err, auth.ErrTelegramStale):
		s.bounce(w, r, "bad_signature")
		return
	case errors.Is(err, store.ErrNotFound):
		// A first-time Telegram sign-in registers the account, so reaching here
		// means the row went missing between being written and being read back
		// -- not the ordinary "has never opened the bot" case it used to be.
		s.bounce(w, r, "no_account")
		return
	case err != nil:
		s.log.Error("telegram callback", "err", err)
		s.bounce(w, r, "internal")
		return
	}

	s.setSessionCookie(w, session)
	s.log.Info("signed in via telegram widget")
	// The signed payload stays in this request's URL and must not survive into
	// the address bar, so the redirect goes to a clean path.
	http.Redirect(w, r, s.returnURL(nextPath(r)), http.StatusSeeOther)
}

// bounce sends a failed sign-in back to the login page with a reason code.
//
// A code, not a message: the login page owns the wording, and a message
// reflected out of a query string is how a redirect becomes a place to put
// text in front of someone under our domain name.
func (s *Server) bounce(w http.ResponseWriter, r *http.Request, reason string) {
	http.Redirect(w, r, s.cfg.BaseURL+"/login?error="+reason, http.StatusSeeOther)
}

// nextPath is the post-login destination, taken from our own query parameter.
//
// `returnURL` re-checks it before use, so an absolute URL smuggled in here
// cannot turn the sign-in flow into an open redirect.
func nextPath(r *http.Request) string {
	requested := r.URL.Query().Get("next")
	if requested == "" {
		return "/app"
	}
	return requested
}
