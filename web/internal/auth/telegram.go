package auth

import (
	"crypto/hmac"
	"crypto/sha256"
	"encoding/hex"
	"errors"
	"fmt"
	"sort"
	"strconv"
	"strings"
	"time"
)

// MaxTelegramAuthAge is how old a login-widget payload may be.
//
// Telegram's own signature never expires, so without this a payload captured
// from a browser's history or a proxy log would authenticate forever.
const MaxTelegramAuthAge = 24 * time.Hour

var (
	ErrTelegramNotConfigured = errors.New("auth: telegram login is not configured")
	ErrTelegramSignature     = errors.New("auth: invalid telegram signature")
	ErrTelegramStale         = errors.New("auth: telegram auth data is too old")
)

// TelegramAuth is the payload Telegram's login widget posts.
type TelegramAuth struct {
	ID        int64  `json:"id"`
	FirstName string `json:"first_name,omitempty"`
	LastName  string `json:"last_name,omitempty"`
	Username  string `json:"username,omitempty"`
	PhotoURL  string `json:"photo_url,omitempty"`
	AuthDate  int64  `json:"auth_date"`
	Hash      string `json:"hash"`
}

// dataCheckString is Telegram's canonical form: every supplied field except
// `hash`, as `key=value`, sorted by key, joined with newlines.
//
// Empty optional fields are omitted rather than sent as `key=`, matching what
// the widget itself signs -- including one would make every check fail.
func (t TelegramAuth) dataCheckString() string {
	fields := map[string]string{
		"id":        strconv.FormatInt(t.ID, 10),
		"auth_date": strconv.FormatInt(t.AuthDate, 10),
	}
	for key, value := range map[string]string{
		"first_name": t.FirstName,
		"last_name":  t.LastName,
		"username":   t.Username,
		"photo_url":  t.PhotoURL,
	} {
		if value != "" {
			fields[key] = value
		}
	}

	keys := make([]string, 0, len(fields))
	for key := range fields {
		keys = append(keys, key)
	}
	sort.Strings(keys)

	lines := make([]string, 0, len(keys))
	for _, key := range keys {
		lines = append(lines, fmt.Sprintf("%s=%s", key, fields[key]))
	}
	return strings.Join(lines, "\n")
}

// VerifyTelegramAuth checks a login-widget payload against the bot token.
//
// Ported from the FastAPI backend's `_validate_telegram_auth`, which was one
// of the few things in it that was already correct. The scheme is Telegram's:
// the HMAC key is SHA-256 of the bot token, not the token itself.
func VerifyTelegramAuth(payload TelegramAuth, botToken string, now time.Time) error {
	if strings.TrimSpace(botToken) == "" {
		return ErrTelegramNotConfigured
	}

	secret := sha256.Sum256([]byte(strings.TrimSpace(botToken)))
	mac := hmac.New(sha256.New, secret[:])
	mac.Write([]byte(payload.dataCheckString()))
	expected := mac.Sum(nil)

	provided, err := hex.DecodeString(strings.TrimSpace(payload.Hash))
	if err != nil {
		return ErrTelegramSignature
	}
	// Constant-time: a byte-by-byte comparison leaks how much of a guessed
	// hash was right, which is enough to forge one.
	if !hmac.Equal(expected, provided) {
		return ErrTelegramSignature
	}

	age := now.Sub(time.Unix(payload.AuthDate, 0))
	if age > MaxTelegramAuthAge || age < -5*time.Minute {
		return ErrTelegramStale
	}
	return nil
}
