package panel

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
	"time"
)

func TestBaseURLNormalisation(t *testing.T) {
	// All the spellings that turn up in real .env files land on one form.
	for _, raw := range []string{
		"https://panel.example.com",
		"https://panel.example.com/",
		"https://panel.example.com/api",
		"https://panel.example.com/api/",
		"panel.example.com",
	} {
		got, err := NormalizeBaseURL(raw)
		if err != nil {
			t.Fatalf("NormalizeBaseURL(%q): %v", raw, err)
		}
		if got != "https://panel.example.com/api" {
			t.Errorf("NormalizeBaseURL(%q) = %q", raw, got)
		}
	}
}

func TestUnusableBaseURLsAreRejected(t *testing.T) {
	// "https://" must not survive as a hostname-less URL that later produces
	// requests to nowhere.
	for _, raw := range []string{"", "   ", "https://"} {
		if _, err := NormalizeBaseURL(raw); err == nil {
			t.Errorf("NormalizeBaseURL(%q) should have failed", raw)
		}
	}
}

func TestPastedBearerPrefixIsStripped(t *testing.T) {
	if got := normalizeToken("Bearer abc123"); got != "abc123" {
		t.Errorf("got %q", got)
	}
	if got := normalizeToken("  bearer  abc123 "); got != "abc123" {
		t.Errorf("got %q", got)
	}
}

func TestPanelUsernameKeepsTelegramAccountsOnTheirExistingName(t *testing.T) {
	// Accounts that came from the bot already have a panel profile named
	// str(telegram_id). Inventing a second name for them would strand the
	// profile they actually use.
	id := int64(123456789)
	if got := Username(&id, "ignored"); got != "123456789" {
		t.Errorf("got %q, want 123456789", got)
	}
}

func TestWebOnlyAccountsGetADerivedName(t *testing.T) {
	got := Username(nil, "3f2504e0-4f89-11d3-9a0c-0305e82c3301")
	if got != "web-3f2504e04f8911d3" {
		t.Errorf("got %q", got)
	}
}

func TestDerivedNamesDifferPerUser(t *testing.T) {
	a := Username(nil, "3f2504e0-4f89-11d3-9a0c-0305e82c3301")
	b := Username(nil, "aaaaaaaa-4f89-11d3-9a0c-0305e82c3301")
	if a == b {
		t.Errorf("two users share the panel name %q", a)
	}
}

// -- transport --------------------------------------------------------------

func testClient(t *testing.T, handler http.HandlerFunc) *Client {
	t.Helper()
	server := httptest.NewServer(handler)
	t.Cleanup(server.Close)

	client, err := New(server.URL, "tok", "", "", time.Second)
	if err != nil {
		t.Fatalf("New: %v", err)
	}
	return client
}

func TestEnvelopeIsUnwrapped(t *testing.T) {
	client := testClient(t, func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte(`{"response":{"uuid":"u1","username":"555","subscriptionUrl":"https://sub/1"}}`))
	})

	user, err := client.UserByUsername(context.Background(), "555")
	if err != nil {
		t.Fatalf("UserByUsername: %v", err)
	}
	if user.UUID != "u1" || user.SubscriptionURL != "https://sub/1" {
		t.Errorf("got %+v", user)
	}
}

func TestAUserNestedUnderResponseUserIsAlsoRead(t *testing.T) {
	// Panel versions differ on this; both shapes have to work.
	client := testClient(t, func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte(`{"response":{"user":{"uuid":"u2","username":"555"}}}`))
	})

	user, err := client.UserByUsername(context.Background(), "555")
	if err != nil {
		t.Fatalf("UserByUsername: %v", err)
	}
	if user.UUID != "u2" {
		t.Errorf("got %+v", user)
	}
}

func TestAMissingUserIsDistinguishable(t *testing.T) {
	// Callers create a profile on this specific error, so it must not be
	// lumped in with transport failures.
	client := testClient(t, func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusNotFound)
	})

	if _, err := client.UserByUsername(context.Background(), "555"); !errors.Is(err, ErrUserNotFound) {
		t.Errorf("expected ErrUserNotFound, got %v", err)
	}
}

func TestRevokeSendsNoBody(t *testing.T) {
	// The panel then generates the new short UUID itself, which its own
	// documentation recommends over supplying one.
	var seenPath, seenMethod string
	var seenBody []byte

	client := testClient(t, func(w http.ResponseWriter, r *http.Request) {
		seenPath, seenMethod = r.URL.Path, r.Method
		seenBody, _ = io.ReadAll(r.Body)
		_, _ = w.Write([]byte(`{"response":{"uuid":"u1","subscriptionUrl":"https://sub/new"}}`))
	})

	user, err := client.RevokeSubscription(context.Background(), "u1")
	if err != nil {
		t.Fatalf("RevokeSubscription: %v", err)
	}
	if seenMethod != http.MethodPost {
		t.Errorf("method = %s, want POST", seenMethod)
	}
	if seenPath != "/api/users/u1/actions/revoke" {
		t.Errorf("path = %s", seenPath)
	}
	if len(seenBody) != 0 {
		t.Errorf("body = %q, want empty", seenBody)
	}
	if user.SubscriptionURL != "https://sub/new" {
		t.Errorf("new url = %q", user.SubscriptionURL)
	}
}

func TestDevicesAreUnwrapped(t *testing.T) {
	client := testClient(t, func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte(`{"response":{"devices":[{"hwid":"a"},{"hwid":"b"}],"total":2}}`))
	})

	devices, err := client.Devices(context.Background(), "u1")
	if err != nil {
		t.Fatalf("Devices: %v", err)
	}
	if len(devices) != 2 || devices[0].HWID != "a" {
		t.Errorf("got %+v", devices)
	}
}

func TestAPanelWithoutDeviceTrackingReportsNoDevices(t *testing.T) {
	// Panels with HWID tracking off answer 404, and an empty list is the
	// honest thing to show for them.
	client := testClient(t, func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusNotFound)
	})

	devices, err := client.Devices(context.Background(), "u1")
	if err != nil {
		t.Fatalf("Devices: %v", err)
	}
	if len(devices) != 0 {
		t.Errorf("got %+v", devices)
	}
}

func TestDeleteNamesBothTheUserAndTheDevice(t *testing.T) {
	var body map[string]string
	var path string

	client := testClient(t, func(w http.ResponseWriter, r *http.Request) {
		path = r.URL.Path
		raw, _ := io.ReadAll(r.Body)
		_ = json.Unmarshal(raw, &body)
		_, _ = w.Write([]byte(`{"response":{"devices":[],"total":0}}`))
	})

	if err := client.DeleteDevice(context.Background(), "u1", "HW-1"); err != nil {
		t.Fatalf("DeleteDevice: %v", err)
	}
	if path != "/api/hwid/devices/delete" {
		t.Errorf("path = %s", path)
	}
	if body["userUuid"] != "u1" || body["hwid"] != "HW-1" {
		t.Errorf("body = %v", body)
	}
}

func TestARefusedDeletionRaisesRatherThanPassingSilently(t *testing.T) {
	// The opposite of the listing case: a silent no-op here would tell a user
	// their device was removed when it was not.
	client := testClient(t, func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusNotFound)
	})

	if err := client.DeleteDevice(context.Background(), "u1", "HW-1"); err == nil {
		t.Fatal("expected an error")
	}
}

func TestAStaticTokenIsNotRetriedOnUnauthorized(t *testing.T) {
	// A 401 against a static token is a configuration problem. Retrying would
	// loop against a panel that will never accept it.
	calls := 0
	client := testClient(t, func(w http.ResponseWriter, r *http.Request) {
		calls++
		w.WriteHeader(http.StatusUnauthorized)
	})

	if _, err := client.UserByUsername(context.Background(), "555"); !errors.Is(err, ErrUnauthorized) {
		t.Errorf("expected ErrUnauthorized, got %v", err)
	}
	if calls != 1 {
		t.Errorf("made %d calls, want 1", calls)
	}
}

func TestAnExpiredLoginTokenTriggersOneRetry(t *testing.T) {
	// A login-issued token can expire mid-flight; re-login and replay once.
	var calls []string
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		calls = append(calls, r.URL.Path)
		if r.URL.Path == "/api/auth/login" {
			token := "stale"
			if len(calls) > 1 {
				token = "fresh"
			}
			_, _ = w.Write([]byte(`{"response":{"accessToken":"` + token + `"}}`))
			return
		}
		if r.Header.Get("Authorization") == "Bearer stale" {
			w.WriteHeader(http.StatusUnauthorized)
			return
		}
		_, _ = w.Write([]byte(`{"response":{"uuid":"u1","username":"555"}}`))
	}))
	defer server.Close()

	client, err := New(server.URL, "", "admin", "secret", time.Second)
	if err != nil {
		t.Fatalf("New: %v", err)
	}

	user, err := client.UserByUsername(context.Background(), "555")
	if err != nil {
		t.Fatalf("UserByUsername: %v", err)
	}
	if user.UUID != "u1" {
		t.Errorf("got %+v", user)
	}
}

func TestNewRequiresSomeCredential(t *testing.T) {
	if _, err := New("https://panel.example.com", "", "", "", time.Second); err == nil {
		t.Fatal("expected an error with no credentials")
	}
}
