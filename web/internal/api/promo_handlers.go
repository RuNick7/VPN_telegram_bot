package api

import (
	"errors"
	"net/http"
	"strings"
	"time"

	"github.com/RuNick7/VPN_telegram_bot/web/internal/store"
)

// Generous enough that nobody mistyping a code from a friend will hit it, far
// too small to search a keyspace with.
const (
	promoAttemptsPerUser = 10
	promoWindow          = time.Hour
)

func (s *Server) handleRedeemPromo(w http.ResponseWriter, r *http.Request, user *store.User) {
	var body struct {
		Code string `json:"code"`
	}
	if err := decodeJSON(r, &body); err != nil {
		writeError(w, http.StatusBadRequest, "bad_request", "Некорректный запрос.")
		return
	}
	code := strings.ToUpper(strings.TrimSpace(body.Code))
	if code == "" {
		writeError(w, http.StatusBadRequest, "invalid_code", "Введите промокод.")
		return
	}

	// A gift code is a bearer credential, and this endpoint says whether a
	// guess was right. Unlimited guesses turn it into an oracle over every
	// unredeemed gift at once, so the attempts are counted per account.
	ok, err := s.store.AllowAttempt(r.Context(), "promo:"+user.ID, promoAttemptsPerUser, promoWindow)
	if err != nil {
		s.fail(w, r, err)
		return
	}
	if !ok {
		writeError(w, http.StatusTooManyRequests, "rate_limited",
			"Слишком много попыток. Попробуйте через час.")
		return
	}

	promo, err := s.store.PromoByCode(r.Context(), code)
	if errors.Is(err, store.ErrNotFound) {
		writeError(w, http.StatusNotFound, "invalid_code", "Промокод недействителен.")
		return
	}
	if err != nil {
		s.fail(w, r, err)
		return
	}
	if !promo.IsActive {
		writeError(w, http.StatusNotFound, "invalid_code", "Промокод недействителен.")
		return
	}
	if promo.Type != "days" && promo.Type != "gift" {
		writeError(w, http.StatusBadRequest, "unsupported_code", "Этот тип промокода пока не поддерживается.")
		return
	}
	// Either handle identifies the buyer. Comparing Telegram IDs alone was a
	// hole rather than a limitation: a gift bought on the site recorded no
	// Telegram ID at all, so its buyer failed this check and could activate
	// the gift they had just paid for.
	if promo.Type == "gift" && boughtBy(promo, user) {
		writeError(w, http.StatusBadRequest, "own_gift", "Нельзя активировать собственный подарочный промокод.")
		return
	}

	// Claim before crediting. A one-time code cannot then be redeemed twice by
	// two people racing each other -- the loser's claim fails and nothing is
	// credited. Same ordering as the bot's promo flow.
	oneTime := promo.OneTime || promo.Type == "gift"
	claimed, err := s.store.ClaimPromo(r.Context(), code, user.ID, user.TelegramID, oneTime)
	if err != nil {
		s.fail(w, r, err)
		return
	}
	if !claimed {
		if oneTime {
			writeError(w, http.StatusConflict, "already_used", "Этот промокод уже был использован.")
		} else {
			writeError(w, http.StatusConflict, "already_used", "Вы уже использовали этот промокод.")
		}
		return
	}

	ctx, cancel := contextWithTimeout(r, panelTimeout)
	defer cancel()

	newEnds, err := s.account.ExtendSubscription(ctx, user, promo.Value)
	if err != nil {
		// Roll the claim back so the user can try again rather than losing the
		// code to a failure that was ours.
		if releaseErr := s.store.ReleasePromo(r.Context(), code, user.ID); releaseErr != nil {
			s.log.Error("release promo after failed credit", "code", code, "err", releaseErr)
		}
		s.log.Error("promo credit", "code", code, "err", err)
		writeError(w, http.StatusBadGateway, "credit_failed", "Не удалось продлить подписку. Попробуйте позже.")
		return
	}

	s.log.Info("promo redeemed", "user", user.ID, "days", promo.Value)
	writeJSON(w, http.StatusOK, map[string]any{
		"days_added": promo.Value,
		"expires_at": newEnds.Unix(),
	})
}
