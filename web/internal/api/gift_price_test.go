package api

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"github.com/RuNick7/VPN_telegram_bot/web/internal/config"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/pricing"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/store"
)

func TestGiftsAreShownAtThePriceTheyAreCharged(t *testing.T) {
	// The gift cards used to be drawn from "plans", which carry the buyer's
	// referral discount, while handleBuyGift charges tier 0: a customer with
	// five friends saw a year's gift for 59 ₽ and was asked 899 ₽. The gift
	// list must be priced the way the gift is charged, whatever the buyer's
	// own tier.
	s := &Server{cfg: &config.Config{}}
	for _, referred := range []int{0, 2, pricing.MaxTier} {
		rec := httptest.NewRecorder()
		s.handlePlans(rec, httptest.NewRequest(http.MethodGet, "/api/plans", nil), &store.User{ReferredPeople: referred})

		var body struct {
			Plans     []pricing.Plan `json:"plans"`
			GiftPlans []pricing.Plan `json:"gift_plans"`
		}
		if err := json.NewDecoder(rec.Body).Decode(&body); err != nil {
			t.Fatalf("referred %d: decode: %v", referred, err)
		}
		if len(body.GiftPlans) == 0 || len(body.GiftPlans) != len(body.Plans) {
			t.Fatalf("referred %d: %d gift plans for %d plans", referred, len(body.GiftPlans), len(body.Plans))
		}
		for _, gift := range body.GiftPlans {
			charged, ok := pricing.SubscriptionPrice(gift.Months, 0) // what handleBuyGift asks
			if !ok || gift.Price != charged {
				t.Errorf("referred %d: %d-month gift shown at %d ₽, charged %d ₽", referred, gift.Months, gift.Price, charged)
			}
		}
		// And the customer's own plans do carry the discount: at the top
		// tier the year must cost less than the same year as a gift.
		if referred == pricing.MaxTier && body.Plans[len(body.Plans)-1].Price >= body.GiftPlans[len(body.GiftPlans)-1].Price {
			t.Errorf("top tier: own year %d ₽ is not below the gift's %d ₽",
				body.Plans[len(body.Plans)-1].Price, body.GiftPlans[len(body.GiftPlans)-1].Price)
		}
	}
}
