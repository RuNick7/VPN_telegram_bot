package auth

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"testing"
	"time"
)

const botToken = "123456:TEST-TOKEN"

// sign produces the hash Telegram's login widget would send, so the tests
// exercise the real scheme rather than a rewritten one.
func sign(t *testing.T, payload TelegramAuth, token string) TelegramAuth {
	t.Helper()
	secret := sha256.Sum256([]byte(token))
	mac := hmac.New(sha256.New, secret[:])
	mac.Write([]byte(payload.dataCheckString()))
	payload.Hash = hex.EncodeToString(mac.Sum(nil))
	return payload
}

func validPayload(t *testing.T) TelegramAuth {
	t.Helper()
	return sign(t, TelegramAuth{
		ID:        555,
		Username:  "someone",
		FirstName: "Имя",
		AuthDate:  time.Now().Unix(),
	}, botToken)
}

func TestValidSignatureIsAccepted(t *testing.T) {
	if err := VerifyTelegramAuth(validPayload(t), botToken, time.Now()); err != nil {
		t.Fatalf("valid payload rejected: %v", err)
	}
}

func TestTamperedFieldIsRejected(t *testing.T) {
	// The whole point of the check: someone editing the user ID to log in as
	// another account must not get through.
	payload := validPayload(t)
	payload.ID = 999

	if err := VerifyTelegramAuth(payload, botToken, time.Now()); !errors.Is(err, ErrTelegramSignature) {
		t.Fatalf("expected a signature error, got %v", err)
	}
}

func TestSignatureFromADifferentBotIsRejected(t *testing.T) {
	payload := sign(t, TelegramAuth{ID: 555, AuthDate: time.Now().Unix()}, "999999:OTHER-BOT")

	if err := VerifyTelegramAuth(payload, botToken, time.Now()); !errors.Is(err, ErrTelegramSignature) {
		t.Fatalf("expected a signature error, got %v", err)
	}
}

func TestMalformedHashIsRejected(t *testing.T) {
	payload := validPayload(t)
	payload.Hash = "not-hex"

	if err := VerifyTelegramAuth(payload, botToken, time.Now()); !errors.Is(err, ErrTelegramSignature) {
		t.Fatalf("expected a signature error, got %v", err)
	}
}

func TestStalePayloadIsRejected(t *testing.T) {
	// Telegram's signature never expires on its own, so a payload lifted from
	// a browser history or a proxy log would otherwise work forever.
	payload := sign(t, TelegramAuth{
		ID:       555,
		AuthDate: time.Now().Add(-48 * time.Hour).Unix(),
	}, botToken)

	if err := VerifyTelegramAuth(payload, botToken, time.Now()); !errors.Is(err, ErrTelegramStale) {
		t.Fatalf("expected a staleness error, got %v", err)
	}
}

func TestFuturePayloadIsRejected(t *testing.T) {
	// A far-future auth_date would otherwise be a way to mint a payload that
	// stays valid past the age limit.
	payload := sign(t, TelegramAuth{
		ID:       555,
		AuthDate: time.Now().Add(time.Hour).Unix(),
	}, botToken)

	if err := VerifyTelegramAuth(payload, botToken, time.Now()); !errors.Is(err, ErrTelegramStale) {
		t.Fatalf("expected a staleness error, got %v", err)
	}
}

func TestMissingBotTokenRefusesRatherThanAccepting(t *testing.T) {
	// An unconfigured deployment must reject logins, not wave them through.
	if err := VerifyTelegramAuth(validPayload(t), "", time.Now()); !errors.Is(err, ErrTelegramNotConfigured) {
		t.Fatalf("expected not-configured, got %v", err)
	}
}

func TestOptionalFieldsAreOmittedNotSentEmpty(t *testing.T) {
	// The widget signs only the fields it actually sends. Including
	// `last_name=` for an absent surname would make every such login fail.
	payload := TelegramAuth{ID: 7, AuthDate: 100, Username: "u"}
	got := payload.dataCheckString()
	want := "auth_date=100\nid=7\nusername=u"

	if got != want {
		t.Fatalf("data-check string:\n got %q\nwant %q", got, want)
	}
}

func TestDataCheckStringIsSortedByKey(t *testing.T) {
	payload := TelegramAuth{ID: 7, AuthDate: 100, FirstName: "A", Username: "u", PhotoURL: "p"}
	want := "auth_date=100\nfirst_name=A\nid=7\nphoto_url=p\nusername=u"

	if got := payload.dataCheckString(); got != want {
		t.Fatalf("data-check string:\n got %q\nwant %q", got, want)
	}
}

// -- email normalisation ----------------------------------------------------

func TestEmailNormalisation(t *testing.T) {
	cases := []struct {
		raw  string
		want string
	}{
		{"User@Example.COM", "user@example.com"},
		{"  bob@example.com  ", "bob@example.com"},
		{"Bob Smith <bob@example.com>", "bob@example.com"},
	}
	for _, tc := range cases {
		got, err := NormalizeEmail(tc.raw)
		if err != nil {
			t.Fatalf("NormalizeEmail(%q): %v", tc.raw, err)
		}
		if got != tc.want {
			t.Errorf("NormalizeEmail(%q) = %q, want %q", tc.raw, got, tc.want)
		}
	}
}

func TestUnusableEmailsAreRejected(t *testing.T) {
	for _, raw := range []string{"", "   ", "not-an-email", "@example.com", "a@"} {
		if _, err := NormalizeEmail(raw); !errors.Is(err, ErrInvalidEmail) {
			t.Errorf("NormalizeEmail(%q) should have failed, got %v", raw, err)
		}
	}
}
