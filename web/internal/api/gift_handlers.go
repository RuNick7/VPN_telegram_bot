package api

import (
	"net/http"

	"github.com/RuNick7/VPN_telegram_bot/web/internal/store"
)

// Gifts a customer has bought, and the two ways to hand each one over.
//
// A gift used to leave the system as a single Telegram message. That works for
// somebody who bought it in the bot and nowhere else: a website account has no
// Telegram ID, so the message went to nobody, and the code -- paid for, valid,
// sitting in the database -- was reachable from no screen at all. This is
// where it lives now, on the page the buyer is returned to after paying.

// boughtBy reports whether this account paid for this code.
//
// Either handle is enough. The Telegram ID is what a bot purchase records and
// what support recognises; the internal id is the one every account has, and
// checking only the former let a website buyer redeem their own gift.
func boughtBy(promo *store.Promo, user *store.User) bool {
	if promo.CreatorUserID != nil && *promo.CreatorUserID == user.ID {
		return true
	}
	return promo.CreatorID != nil && user.TelegramID != nil && *promo.CreatorID == *user.TelegramID
}

type giftBody struct {
	Code string `json:"code"`
	Link string `json:"link"`
	Days int    `json:"days"`
	// Unix seconds. Redeemed is nil while the gift is still waiting to be used,
	// which is the state the buyer needs to act on.
	CreatedAt int64  `json:"created_at"`
	Redeemed  *int64 `json:"redeemed_at"`
}

func (s *Server) handleListGifts(w http.ResponseWriter, r *http.Request, user *store.User) {
	gifts, err := s.store.GiftsCreatedBy(r.Context(), user.ID)
	if err != nil {
		s.fail(w, r, err)
		return
	}

	body := make([]giftBody, 0, len(gifts))
	for _, gift := range gifts {
		item := giftBody{
			Code: gift.Code,
			// Built here rather than stored, so a change of domain does not
			// leave old gifts pointing at the previous one. Empty when no
			// public origin is configured -- the code alone still works.
			Link:      s.giftLink(gift.Code),
			Days:      gift.Days,
			CreatedAt: gift.CreatedAt.Unix(),
		}
		if gift.RedeemedAt != nil {
			redeemed := gift.RedeemedAt.Unix()
			item.Redeemed = &redeemed
		}
		body = append(body, item)
	}
	writeJSON(w, http.StatusOK, map[string]any{"gifts": body})
}

// giftLink is the address that redeems a code without Telegram.
//
// Kept identical to Settings.gift_link on the Python side, which the bot uses
// for the same code. Both routes redeem the same one-time code, so a gift
// handed over twice is still a gift used once.
func (s *Server) giftLink(code string) string {
	if s.cfg.BaseURL == "" {
		return ""
	}
	return s.cfg.BaseURL + "/gift/" + code
}
