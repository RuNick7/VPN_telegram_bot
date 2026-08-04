package account

import (
	"context"
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"

	"github.com/RuNick7/VPN_telegram_bot/web/internal/panel"
)

// squadPanel answers the squad listing with two squads and records nothing
// else -- placement is the only thing under test here.
func squadPanel(t *testing.T) *panel.Client {
	t.Helper()
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_ = json.NewEncoder(w).Encode(map[string]any{
			"response": map[string]any{"internalSquads": []map[string]any{
				{"uuid": "paid-uuid", "name": "internal"},
				{"uuid": "lte-uuid", "name": "LTE"},
			}},
		})
	}))
	t.Cleanup(server.Close)

	client, err := panel.New(server.URL, "token", "", "", 5*time.Second)
	if err != nil {
		t.Fatalf("panel.New: %v", err)
	}
	return client
}

func TestANewAccountJoinsTheMeteredSquadToo(t *testing.T) {
	// The bug: an account was shown its free gigabytes the moment it was
	// created and could not reach the servers those gigabytes are for.
	// Membership came only from the traffic monitor, on its own schedule, and
	// only once it had found a metered node -- with none, never at all.
	svc := NewService(nil, squadPanel(t), false, 7, "internal", true, "LTE")

	squads, err := svc.paidSquad(context.Background())
	if err != nil {
		t.Fatalf("paidSquad: %v", err)
	}
	if len(squads) != 2 || squads[0] != "paid-uuid" || squads[1] != "lte-uuid" {
		t.Errorf("got %v, want both the paid and the metered squad", squads)
	}
}

func TestTheMeteredSquadIsSkippedWhenQuotasAreOff(t *testing.T) {
	svc := NewService(nil, squadPanel(t), false, 7, "internal", false, "LTE")

	squads, err := svc.paidSquad(context.Background())
	if err != nil {
		t.Fatalf("paidSquad: %v", err)
	}
	if len(squads) != 1 || squads[0] != "paid-uuid" {
		t.Errorf("got %v, want the paid squad alone", squads)
	}
}

func TestAMissingMeteredSquadDoesNotStopTheAccount(t *testing.T) {
	// LTE is an extra. An account without it still reaches everything else,
	// and the monitor adds it later -- refusing to create the account would
	// trade a missing extra for no service at all.
	svc := NewService(nil, squadPanel(t), false, 7, "internal", true, "no-such-squad")

	squads, err := svc.paidSquad(context.Background())
	if err != nil {
		t.Fatalf("paidSquad: %v", err)
	}
	if len(squads) != 1 || squads[0] != "paid-uuid" {
		t.Errorf("got %v, want the paid squad alone", squads)
	}
}

func TestAMissingPaidSquadIsFatal(t *testing.T) {
	// The opposite call: with no paid squad the account reaches nothing, and
	// that failure only surfaces when the customer tries to connect.
	svc := NewService(nil, squadPanel(t), false, 7, "no-such-squad", false, "")

	if _, err := svc.paidSquad(context.Background()); err == nil {
		t.Error("expected an error when the paid squad does not exist")
	}
}
