package config

import (
	"strings"
	"testing"
)

func complete() *Config {
	return &Config{
		DatabaseURL: "postgres://u:p@localhost/db",
		BaseURL:     "https://cabinet.example.com",
		SMTP:        SMTP{Host: "smtp.example.com", From: "no-reply@example.com"},
		Remnawave:   Remnawave{BaseURL: "https://panel.example.com", Token: "tok"},
	}
}

func TestACompleteConfigValidates(t *testing.T) {
	if err := complete().Validate(); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestStartupRefusesWithoutASender(t *testing.T) {
	// The previous backend, with no real sender, put the magic-link token in
	// the API response -- so "email verification" verified nothing and anyone
	// could claim any address. Refusing to start is the alternative to
	// silently shipping that again.
	cfg := complete()
	cfg.SMTP = SMTP{}

	err := cfg.Validate()
	if err == nil {
		t.Fatal("expected startup to fail without SMTP")
	}
	if !strings.Contains(err.Error(), "SMTP_HOST") {
		t.Errorf("error should name the missing setting, got: %v", err)
	}
}

func TestStartupRefusesWithoutPanelCredentials(t *testing.T) {
	cfg := complete()
	cfg.Remnawave.Token = ""

	if err := cfg.Validate(); err == nil {
		t.Fatal("expected startup to fail without panel credentials")
	}
}

func TestUsernameAndPasswordAreAnAcceptableAlternativeToAToken(t *testing.T) {
	cfg := complete()
	cfg.Remnawave.Token = ""
	cfg.Remnawave.Username, cfg.Remnawave.Password = "admin", "secret"

	if err := cfg.Validate(); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
}

func TestStartupRefusesWithoutABaseURL(t *testing.T) {
	// Magic links are built from it; without one they would point nowhere.
	cfg := complete()
	cfg.BaseURL = ""

	if err := cfg.Validate(); err == nil {
		t.Fatal("expected startup to fail without WEB_BASE_URL")
	}
}

func TestEveryProblemIsReportedAtOnce(t *testing.T) {
	// Fixing configuration one restart at a time is miserable.
	err := (&Config{}).Validate()
	if err == nil {
		t.Fatal("expected an error")
	}
	for _, want := range []string{"DATABASE_URL", "WEB_BASE_URL", "SMTP_HOST", "REMNAWAVE_BASE_URL"} {
		if !strings.Contains(err.Error(), want) {
			t.Errorf("error should mention %s, got: %v", want, err)
		}
	}
}

func TestOptionalFeaturesDoNotBlockStartup(t *testing.T) {
	// Email is a complete login route on its own, and the site is useful
	// read-only without payments configured.
	cfg := complete()
	if err := cfg.Validate(); err != nil {
		t.Fatalf("unexpected error: %v", err)
	}
	if cfg.TelegramLoginEnabled() {
		t.Error("Telegram login should be off without a bot token")
	}
	if cfg.PaymentsEnabled() {
		t.Error("payments should be off without YooKassa credentials")
	}
}

func TestDotEnvParsing(t *testing.T) {
	cases := []struct {
		line      string
		key, want string
		ok        bool
	}{
		{`FOO=bar`, "FOO", "bar", true},
		{`FOO="bar baz"`, "FOO", "bar baz", true},
		{`FOO='bar'`, "FOO", "bar", true},
		{`  FOO = bar  `, "FOO", "bar", true},
		{`export FOO=bar`, "FOO", "bar", true},
		{`# comment`, "", "", false},
		{``, "", "", false},
		{`no-equals-sign`, "", "", false},
		// A value containing '=' must survive intact; base64 secrets end in
		// padding and splitting on every '=' would truncate them.
		{`FOO=a=b=c`, "FOO", "a=b=c", true},
	}
	for _, tc := range cases {
		key, value, ok := parseDotEnvLine(tc.line)
		if ok != tc.ok || key != tc.key || value != tc.want {
			t.Errorf("parse(%q) = (%q, %q, %v), want (%q, %q, %v)",
				tc.line, key, value, ok, tc.key, tc.want, tc.ok)
		}
	}
}
