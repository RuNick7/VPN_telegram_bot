package api

import (
	"crypto/rand"
	"encoding/base64"
	"net/http"
	"net/url"
	"time"

	"github.com/RuNick7/VPN_telegram_bot/web/internal/store"
)

// linkTokenTTL is how long a Telegram-link invitation stays usable.
//
// Short, because the whole flow is "click here, then press start" and anything
// left lying around afterwards is a credential that attaches someone else's
// Telegram account to this one.
const linkTokenTTL = 15 * time.Minute

// handleCreateTelegramLink mints a one-time link that attaches a Telegram
// account to this one.
//
// The token travels in a `t.me/<bot>?start=link_<token>` deep link. That is
// the whole handshake: only the holder of this session could have been given
// the link, and only someone in the chat can redeem it, so the two ends are
// the same person by construction and neither has to type an ID at the other.
func (s *Server) handleCreateTelegramLink(w http.ResponseWriter, r *http.Request, user *store.User) {
	if !s.cfg.TelegramLoginEnabled() || s.cfg.TelegramBotUsername == "" {
		writeError(w, http.StatusNotImplemented, "not_configured", "Привязка Telegram не настроена.")
		return
	}
	if user.TelegramID != nil {
		writeError(w, http.StatusConflict, "already_linked", "Telegram уже привязан к этому аккаунту.")
		return
	}

	token, err := randomToken()
	if err != nil {
		s.fail(w, r, err)
		return
	}
	if err := s.store.CreateLinkToken(r.Context(), token, user.ID, linkTokenTTL); err != nil {
		s.fail(w, r, err)
		return
	}

	deepLink := "https://t.me/" + url.PathEscape(s.cfg.TelegramBotUsername) +
		"?start=link_" + url.QueryEscape(token)

	writeJSON(w, http.StatusOK, map[string]any{
		"url":        deepLink,
		"expires_in": int(linkTokenTTL.Seconds()),
		"detail": "Откройте ссылку и нажмите «Start» в боте. " +
			"Дни подписки с обоих аккаунтов сложатся.",
	})
}

// handleLinkStatus reports whether this account has a Telegram identity yet,
// so the cabinet can show either the link button or the linked state without
// the client inferring it from other endpoints.
func (s *Server) handleLinkStatus(w http.ResponseWriter, r *http.Request, user *store.User) {
	pending, err := s.store.HasPendingLinkToken(r.Context(), user.ID)
	if err != nil {
		s.fail(w, r, err)
		return
	}
	writeJSON(w, http.StatusOK, s.linkStatus(user, pending))
}

// linkStatus is what the cabinet needs to draw either half of the Telegram
// block, including whether detaching is offered at all.
func (s *Server) linkStatus(user *store.User, pending bool) map[string]any {
	return map[string]any{
		"linked":       user.TelegramID != nil,
		"telegram_tag": user.TelegramTag,
		"link_pending": pending,
		"can_link":     user.TelegramID == nil && s.cfg.TelegramLoginEnabled(),
		// Detaching leaves the address as the only way in, so an account
		// without one cannot be allowed to do it: there would be no route back.
		"can_unlink":   user.TelegramID != nil && user.Email != "",
		"telegram_bot": s.cfg.TelegramBotUsername,
	}
}

// handleUnlinkTelegram detaches the Telegram identity from this account.
//
// Everything the account owns stays with it -- subscription, traffic,
// referrals, panel profile -- because none of it belonged to the Telegram
// side. What changes is who can sign in as this account, which is why it is
// refused outright when no address has been confirmed: the customer would be
// deleting their own last key.
func (s *Server) handleUnlinkTelegram(w http.ResponseWriter, r *http.Request, user *store.User) {
	if user.TelegramID == nil {
		writeError(w, http.StatusConflict, "not_linked", "Telegram и так не привязан.")
		return
	}
	if user.Email == "" {
		writeError(w, http.StatusConflict, "no_other_login",
			"Сначала добавьте почту — иначе войти в аккаунт будет нечем.")
		return
	}

	detached, err := s.store.DetachTelegram(r.Context(), user.ID)
	if err != nil {
		s.fail(w, r, err)
		return
	}
	if !detached {
		writeError(w, http.StatusConflict, "not_linked", "Telegram и так не привязан.")
		return
	}

	s.log.Info("telegram unlinked", "user", user.ID)
	// Answered with the fresh state so the page redraws from the server's view
	// rather than guessing what it now is.
	user.TelegramID = nil
	user.TelegramTag = ""
	writeJSON(w, http.StatusOK, s.linkStatus(user, false))
}

// randomToken returns 256 bits of entropy, URL-safe. crypto/rand because this
// value is the credential.
func randomToken() (string, error) {
	buf := make([]byte, 32)
	if _, err := rand.Read(buf); err != nil {
		return "", err
	}
	return base64.RawURLEncoding.EncodeToString(buf), nil
}
