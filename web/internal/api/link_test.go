package api

import (
	"testing"

	"github.com/RuNick7/VPN_telegram_bot/web/internal/store"
)

// Whether detaching Telegram is offered at all.
//
// The rule is worth pinning because getting it wrong locks somebody out of
// their own account: Telegram and the email address are the only two ways in,
// and removing one when the other is missing leaves none.

func TestUnlinkingIsOfferedWhenThereIsAnotherWayIn(t *testing.T) {
	server := serverWith(7, true)
	status := server.linkStatus(&store.User{
		TelegramID: ptrInt64(555),
		Email:      "customer@example.com",
	}, false)

	if status["can_unlink"] != true {
		t.Fatalf("can_unlink = %v, want true", status["can_unlink"])
	}
}

func TestUnlinkingIsRefusedWithoutAnAddress(t *testing.T) {
	// The account would have no sign-in route left at all -- and no way to get
	// one, because adding an address is done from inside the cabinet.
	server := serverWith(7, true)
	status := server.linkStatus(&store.User{TelegramID: ptrInt64(555)}, false)

	if status["can_unlink"] != false {
		t.Fatalf("can_unlink = %v, want false for an account with no email", status["can_unlink"])
	}
}

func TestThereIsNothingToUnlinkWithoutTelegram(t *testing.T) {
	server := serverWith(7, true)
	status := server.linkStatus(&store.User{Email: "customer@example.com"}, false)

	if status["can_unlink"] != false {
		t.Fatalf("can_unlink = %v, want false", status["can_unlink"])
	}
	if status["can_link"] != true {
		t.Fatalf("can_link = %v, want true", status["can_link"])
	}
}

func TestLinkingIsNotOfferedWithoutAConfiguredBot(t *testing.T) {
	// The endpoint answers 501 without one, so the button would be there only
	// to fail.
	server := serverWith(7, false)
	status := server.linkStatus(&store.User{Email: "customer@example.com"}, false)

	if status["can_link"] != false {
		t.Fatalf("can_link = %v, want false", status["can_link"])
	}
}

func TestAnUnlinkedAccountReportsNoTag(t *testing.T) {
	// What the handler answers with after detaching. The tag goes with the
	// identity: leaving it behind would let two accounts claim the same
	// referral handle once that Telegram is attached somewhere else.
	server := serverWith(7, true)
	status := server.linkStatus(&store.User{Email: "customer@example.com"}, false)

	if status["linked"] != false || status["telegram_tag"] != "" {
		t.Fatalf("got linked=%v tag=%q", status["linked"], status["telegram_tag"])
	}
}
