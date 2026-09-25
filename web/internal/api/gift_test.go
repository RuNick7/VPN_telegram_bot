package api

import (
	"testing"

	"github.com/RuNick7/VPN_telegram_bot/web/internal/store"
)

// Who is allowed to redeem a gift.
//
// This is worth pinning because getting it wrong is free money in one
// direction and a refused purchase in the other: a buyer who can activate
// their own gift has bought a discount, and a recipient wrongly refused has
// been handed a code that does not work.

func ptrInt64(v int64) *int64    { return &v }
func ptrString(v string) *string { return &v }

const (
	buyerID     = "3f2504e0-4f89-11d3-9a0c-0305e82c3301"
	recipientID = "aaaaaaaa-4f89-11d3-9a0c-0305e82c3301"
)

func TestAWebsiteBuyerCannotRedeemTheirOwnGift(t *testing.T) {
	// The hole this closed. A gift bought on the site records no Telegram ID,
	// so a check that compared only those found nothing to compare and let the
	// buyer activate the code they had just paid for.
	promo := &store.Promo{Type: "gift", CreatorUserID: ptrString(buyerID)}
	if !boughtBy(promo, &store.User{ID: buyerID}) {
		t.Fatal("the buyer should be recognised by their internal id")
	}
}

func TestABotBuyerCannotRedeemTheirOwnGiftEither(t *testing.T) {
	// Codes bought before creator_user_id existed carry only the Telegram ID,
	// and must keep being refused.
	promo := &store.Promo{Type: "gift", CreatorID: ptrInt64(555)}
	if !boughtBy(promo, &store.User{ID: buyerID, TelegramID: ptrInt64(555)}) {
		t.Fatal("a legacy gift should still be recognised by its Telegram ID")
	}
}

func TestSomebodyElseCanRedeemTheGift(t *testing.T) {
	promo := &store.Promo{
		Type:          "gift",
		CreatorID:     ptrInt64(555),
		CreatorUserID: ptrString(buyerID),
	}
	recipient := &store.User{ID: recipientID, TelegramID: ptrInt64(999)}
	if boughtBy(promo, recipient) {
		t.Fatal("the recipient is not the buyer and must be able to redeem")
	}
}

func TestAnOperatorCodeBelongsToNobody(t *testing.T) {
	// Promo codes made in the admin bot have no creator of either kind. Every
	// account must be able to use one.
	promo := &store.Promo{Type: "days"}
	if boughtBy(promo, &store.User{ID: buyerID, TelegramID: ptrInt64(555)}) {
		t.Fatal("a code with no creator must not be treated as somebody's own")
	}
}

func TestTheGiftLinkIsBuiltFromTheConfiguredOrigin(t *testing.T) {
	// Built per request rather than stored with the code, so moving domains
	// does not leave old gifts pointing at the previous one.
	server := serverWith(7, false)
	server.cfg.BaseURL = "https://kairavpn.pro"
	if got := server.giftLink("GIFT-ABC123"); got != "https://kairavpn.pro/gift/GIFT-ABC123" {
		t.Fatalf("giftLink = %q", got)
	}
}

func TestThereIsNoGiftLinkWithoutAnOrigin(t *testing.T) {
	// An empty string, not "/gift/CODE": a relative path pasted into a chat
	// window goes nowhere, and the code on its own still works in the bot.
	if got := serverWith(7, false).giftLink("GIFT-ABC123"); got != "" {
		t.Fatalf("giftLink = %q, want empty when WEB_BASE_URL is unset", got)
	}
}
