package api

import (
	"testing"

	"github.com/RuNick7/VPN_telegram_bot/web/internal/config"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/store"
)

// Which offer an account sees, if any.
//
// Worth pinning because every branch is a decision about free days: offering
// the wrong direction wastes the one interruption the customer will tolerate,
// and offering it to somebody who has already collected would promise days
// that the guarded flag then refuses to pay.

func serverWith(bonusDays int, telegram bool) *Server {
	cfg := &config.Config{TrialLinkBonusDays: bonusDays}
	if telegram {
		cfg.TelegramBotToken = "123:token"
		cfg.TelegramBotUsername = "KairaBot"
	}
	return &Server{cfg: cfg}
}

func telegramID(id int64) *int64 { return &id }

func TestAnEmailAccountIsOfferedTelegram(t *testing.T) {
	offer := serverWith(7, true).bonusOffer(&store.User{Email: "a@example.com"})
	if offer.Kind != "telegram" || offer.Days != 7 {
		t.Fatalf("got %+v, want a telegram offer worth 7", offer)
	}
}

func TestATelegramAccountIsOfferedEmail(t *testing.T) {
	offer := serverWith(7, true).bonusOffer(&store.User{TelegramID: telegramID(555)})
	if offer.Kind != "email" {
		t.Fatalf("got %+v, want an email offer", offer)
	}
}

func TestAnAccountWithBothIdentitiesIsOfferedNothing(t *testing.T) {
	// There is nothing left to connect, so there is nothing to pay for.
	offer := serverWith(7, true).bonusOffer(&store.User{
		Email:      "a@example.com",
		TelegramID: telegramID(555),
	})
	if offer.Kind != "" {
		t.Fatalf("got %+v, want no offer", offer)
	}
}

func TestACollectedBonusIsNeverOfferedAgain(t *testing.T) {
	offer := serverWith(7, true).bonusOffer(&store.User{
		Email:            "a@example.com",
		TrialLinkGranted: true,
	})
	if offer.Kind != "" {
		t.Fatalf("got %+v, want no offer once it has been paid", offer)
	}
}

func TestADismissedOfferStaysDismissed(t *testing.T) {
	// Recorded on the account rather than in the browser, so the same answer
	// holds in the bot -- being asked again elsewhere is what makes it nagging.
	offer := serverWith(7, true).bonusOffer(&store.User{
		Email:               "a@example.com",
		BonusOfferDismissed: true,
	})
	if offer.Kind != "" || !offer.Dismissed {
		t.Fatalf("got %+v, want a dismissed offer with no kind", offer)
	}
}

func TestNothingIsOfferedWhenTheBonusIsSwitchedOff(t *testing.T) {
	offer := serverWith(0, true).bonusOffer(&store.User{Email: "a@example.com"})
	if offer.Kind != "" {
		t.Fatalf("got %+v, want no offer when TRIAL_LINK_BONUS_DAYS is 0", offer)
	}
}

func TestAnEmailAccountFallsBackToNothingWithoutTelegramLogin(t *testing.T) {
	// Offering "attach Telegram" with no bot configured leads to an endpoint
	// that answers 501. Better to say nothing than to promise a dead button.
	offer := serverWith(7, false).bonusOffer(&store.User{Email: "a@example.com"})
	if offer.Kind != "" {
		t.Fatalf("got %+v, want no offer without a configured bot", offer)
	}
}

func TestAnAccountWithNeitherIdentityIsOfferedTelegramFirst(t *testing.T) {
	// It cannot really happen -- an account arrives through one door or the
	// other -- but the order is what decides the answer if it ever does, and
	// Telegram is one tap against typing an address and waiting for a letter.
	offer := serverWith(7, true).bonusOffer(&store.User{})
	if offer.Kind != "telegram" {
		t.Fatalf("got %+v, want the cheaper of the two", offer)
	}
}
