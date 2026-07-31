package api

import (
	"errors"
	"net/http"
	"strings"

	"github.com/RuNick7/VPN_telegram_bot/web/internal/store"
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

	// promo_usage is keyed by telegram_id, so redemption is unavailable to an
	// account that has never been linked to Telegram. Saying so is better than
	// failing on a foreign-key violation.
	if user.TelegramID == nil {
		writeError(w, http.StatusConflict, "telegram_required",
			"Промокоды пока доступны только аккаунтам с привязанным Telegram.")
		return
	}
	telegramID := *user.TelegramID

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
	if promo.Type == "gift" && promo.CreatorID != nil && *promo.CreatorID == telegramID {
		writeError(w, http.StatusBadRequest, "own_gift", "Нельзя активировать собственный подарочный промокод.")
		return
	}

	// Claim before crediting. A one-time code cannot then be redeemed twice by
	// two people racing each other -- the loser's claim fails and nothing is
	// credited. Same ordering as the bot's promo flow.
	oneTime := promo.OneTime || promo.Type == "gift"
	claimed, err := s.store.ClaimPromo(r.Context(), code, telegramID, oneTime)
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
		if releaseErr := s.store.ReleasePromo(r.Context(), code, telegramID); releaseErr != nil {
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
