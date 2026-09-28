package api

import (
	"errors"
	"net/http"

	"github.com/RuNick7/VPN_telegram_bot/web/internal/auth"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/store"
)

// The second half of the free period: days paid for connecting the identity an
// account arrived without.
//
// An account with one identity can be locked out of it -- a Telegram ban, a
// lost number, a mailbox that stops being read -- and the subscription goes
// with it. Paying for the second one is not only a growth trick; it is what
// makes the account recoverable, which is why the offer is worth interrupting
// somebody with once.
//
// Which direction is offered depends on what is missing, and both ends pay from
// the same guarded flag, so the bonus lands exactly once whichever way round it
// happens.

type bonusOfferBody struct {
	// Kind is "telegram", "email", or "" when there is nothing to offer.
	Kind      string `json:"kind"`
	Days      int    `json:"days"`
	Dismissed bool   `json:"dismissed"`
}

// bonusOffer works out what this account is still missing.
//
// Nothing is offered once the bonus has been collected, once the customer has
// said stop, or when it is switched off -- and nothing is offered to an account
// that already has both identities, which has nothing left to connect.
func (s *Server) bonusOffer(user *store.User) bonusOfferBody {
	offer := bonusOfferBody{Days: s.cfg.TrialLinkBonusDays, Dismissed: user.BonusOfferDismissed}
	if s.cfg.TrialLinkBonusDays <= 0 || user.TrialLinkGranted || user.BonusOfferDismissed {
		return offer
	}
	switch {
	case user.TelegramID == nil && s.cfg.TelegramLoginEnabled() && s.cfg.TelegramBotUsername != "":
		offer.Kind = "telegram"
	case user.Email == "":
		offer.Kind = "email"
	}
	return offer
}

func (s *Server) handleBonusOffer(w http.ResponseWriter, r *http.Request, user *store.User) {
	writeJSON(w, http.StatusOK, s.bonusOffer(user))
}

func (s *Server) handleDismissBonusOffer(w http.ResponseWriter, r *http.Request, user *store.User) {
	if err := s.store.DismissBonusOffer(r.Context(), user.ID); err != nil {
		s.fail(w, r, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"status": "dismissed"})
}

// handleRequestEmailConfirmation posts the letter that binds an address.
//
// Unlike PATCH /api/me/email this writes nothing now. That endpoint changes an
// address the account already proved; this one adds the first, and an unproved
// address is a way into the account -- one typo would hand a stranger's mailbox
// the ability to request a sign-in link for it.
func (s *Server) handleRequestEmailConfirmation(w http.ResponseWriter, r *http.Request, user *store.User) {
	var body struct {
		Email string `json:"email"`
	}
	if err := decodeJSON(r, &body); err != nil {
		writeError(w, http.StatusBadRequest, "bad_request", "Некорректный запрос.")
		return
	}

	address, err := s.auth.RequestEmailConfirmation(r.Context(), user.ID, body.Email, s.cfg.TrialLinkBonusDays)
	switch {
	case errors.Is(err, auth.ErrInvalidEmail):
		writeError(w, http.StatusBadRequest, "invalid_email", "Проверьте адрес почты.")
		return
	case errors.Is(err, auth.ErrRateLimited):
		writeError(w, http.StatusTooManyRequests, "rate_limited",
			"Слишком много писем. Подождите немного и попробуйте снова.")
		return
	case err != nil:
		// A send failure is ours, not the caller's, and the address may be
		// perfectly good -- so it is reported as our problem, not theirs.
		s.log.Error("email confirmation", "err", err)
		writeError(w, http.StatusBadGateway, "mail_failed", "Не удалось отправить письмо. Попробуйте позже.")
		return
	}

	writeJSON(w, http.StatusOK, map[string]any{
		"status":     "sent",
		"email":      address,
		"expires_in": int(auth.EmailConfirmTTL.Seconds()),
		"detail":     "Письмо отправлено. Откройте ссылку из него, чтобы подтвердить адрес.",
	})
}

// handleConfirmEmail redeems the link from that letter.
//
// Unauthenticated on purpose: the token is the credential, it names one
// account, and the letter is routinely opened on a phone that has never signed
// in. Requiring a session as well would break the ordinary case to defend
// against nothing -- whoever holds the token has already proved the mailbox.
func (s *Server) handleConfirmEmail(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Token string `json:"token"`
	}
	if err := decodeJSON(r, &body); err != nil || body.Token == "" {
		writeError(w, http.StatusBadRequest, "bad_request", "Некорректный запрос.")
		return
	}

	verification, err := s.auth.ConfirmEmail(r.Context(), body.Token)
	if errors.Is(err, auth.ErrBadToken) {
		writeError(w, http.StatusUnauthorized, "bad_token",
			"Ссылка недействительна, истекла или уже была использована.")
		return
	}
	if err != nil {
		s.fail(w, r, err)
		return
	}

	bound, err := s.store.SetConfirmedEmail(r.Context(), verification.UserID, verification.Email)
	if err != nil {
		s.fail(w, r, err)
		return
	}
	if !bound {
		// Somebody else holds the address. Not merged and not stolen: joining
		// two real accounts is what the Telegram handshake is for, and it is a
		// decision the customer makes rather than one a letter makes for them.
		writeError(w, http.StatusConflict, "email_taken",
			"Этот адрес уже привязан к другому аккаунту. Войдите по нему или напишите в поддержку.")
		return
	}

	// Only after the address has actually landed. Paying first would credit
	// days for a binding that then failed, and the flag would stop it ever
	// being paid again.
	granted := 0
	if s.cfg.TrialLinkBonusDays > 0 {
		_, paid, err := s.store.GrantLinkBonus(r.Context(), verification.UserID, s.cfg.TrialLinkBonusDays)
		if err != nil {
			// The address is bound, which is what the customer asked for. A
			// failure to pay is ours to notice, not a reason to tell them the
			// confirmation did not work.
			s.log.Error("link bonus", "err", err, "user", verification.UserID)
		} else if paid {
			granted = s.cfg.TrialLinkBonusDays
		}
	}

	s.log.Info("email confirmed", "user", verification.UserID, "bonus_days", granted)
	writeJSON(w, http.StatusOK, map[string]any{
		"email":      verification.Email,
		"bonus_days": granted,
		"status":     "confirmed",
	})
}
