package api

import (
	"io"
	"log/slog"
	"net/http"
	"net/http/httptest"
	"strings"
	"sync"
	"testing"
	"time"

	"github.com/RuNick7/VPN_telegram_bot/web/internal/account"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/config"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/panel"
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

// -- the panel profile has to be pinned down before the ID goes -------------
//
// For an account created before the identity rework, `telegram_id` *is* the
// handle to its panel profile: the profile is named after it and
// `remnawave_uuid` is only filled in on first lookup. Clearing the ID first
// left nothing that could find the account -- the next request built a second
// profile and the customer's configured link stopped being the managed one.

// deadPanel fails every request and remembers what it was asked for.
func deadPanel(t *testing.T, asked *[]string, mu *sync.Mutex) *panel.Client {
	t.Helper()
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		mu.Lock()
		*asked = append(*asked, r.URL.Path)
		mu.Unlock()
		w.WriteHeader(http.StatusInternalServerError)
	}))
	t.Cleanup(server.Close)

	client, err := panel.New(server.URL, "token", "", "", 2*time.Second)
	if err != nil {
		t.Fatalf("panel.New: %v", err)
	}
	return client
}

// unlinkServer wires a handler whose store is nil on purpose: reaching
// DetachTelegram would panic, so the test cannot pass by accident if the guard
// is removed.
func unlinkServer(t *testing.T, asked *[]string, mu *sync.Mutex) *Server {
	t.Helper()
	return &Server{
		cfg:     &config.Config{TelegramBotToken: "123:token", TelegramBotUsername: "KairaBot"},
		account: account.NewService(nil, deadPanel(t, asked, mu), false, 7, "internal", false, ""),
		log:     slog.New(slog.NewTextHandler(io.Discard, nil)),
	}
}

func TestUnlinkingIsRefusedWhileThePanelCannotBeReached(t *testing.T) {
	var asked []string
	var mu sync.Mutex
	server := unlinkServer(t, &asked, &mu)

	recorder := httptest.NewRecorder()
	server.handleUnlinkTelegram(recorder, httptest.NewRequest(http.MethodPost, "/api/me/telegram", nil),
		&store.User{ID: "user-1", TelegramID: ptrInt64(555), Email: "customer@example.com"})

	if recorder.Code != http.StatusBadGateway {
		t.Fatalf("status = %d, want %d", recorder.Code, http.StatusBadGateway)
	}
}

func TestUnlinkingLooksTheLegacyNameUpBeforeDestroyingIt(t *testing.T) {
	// `str(telegram_id)` is the name a pre-rework profile carries, and asking
	// for it is what records the UUID that outlives the unlink.
	var asked []string
	var mu sync.Mutex
	server := unlinkServer(t, &asked, &mu)

	server.handleUnlinkTelegram(httptest.NewRecorder(),
		httptest.NewRequest(http.MethodPost, "/api/me/telegram", nil),
		&store.User{ID: "user-1", TelegramID: ptrInt64(555), Email: "customer@example.com"})

	mu.Lock()
	defer mu.Unlock()
	for _, path := range asked {
		if strings.Contains(path, "555") {
			return
		}
	}
	t.Fatalf("the panel was never asked about the legacy name; asked for %v", asked)
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
