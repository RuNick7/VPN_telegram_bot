package mailer

import (
	"errors"
	"strings"
	"testing"
	"time"
)

func TestDescribeNeverPrintsThePassword(t *testing.T) {
	// Describe() is written to a terminal by --check-smtp, and terminals get
	// pasted into chat when someone asks for help. The API key must not be in
	// what they paste.
	const secret = "6cba1f8e-secret-api-key"
	m, err := New(Config{
		Host: "smtp.go1.unisender.ru", Port: 587, StartTLS: true,
		Username: "kaira", Password: secret, From: "noreply@kairavpn.pro",
	})
	if err != nil {
		t.Fatal(err)
	}

	got := m.Describe()
	if strings.Contains(got, secret) {
		t.Fatalf("the password is in the output:\n%s", got)
	}
	// The length is what makes a trailing space or a truncated paste visible.
	if !strings.Contains(got, "23 chars") {
		t.Errorf("password length not reported:\n%s", got)
	}
	for _, want := range []string{"smtp.go1.unisender.ru:587", "STARTTLS", "noreply@kairavpn.pro", "kaira"} {
		if !strings.Contains(got, want) {
			t.Errorf("missing %q:\n%s", want, got)
		}
	}
}

func TestDescribeNamesTheTLSModeBothWays(t *testing.T) {
	// The port/mode pairing is the most common misconfiguration, so the mode
	// has to be legible without knowing what `false` means.
	implicit, _ := New(Config{Host: "smtp.yandex.ru", Port: 465, From: "a@b.c"})
	if got := implicit.Describe(); !strings.Contains(got, "implicit TLS") {
		t.Errorf("port 465 mode not described:\n%s", got)
	}

	starttls, _ := New(Config{Host: "smtp.example", Port: 587, StartTLS: true, From: "a@b.c"})
	if got := starttls.Describe(); !strings.Contains(got, "STARTTLS") {
		t.Errorf("port 587 mode not described:\n%s", got)
	}
}

func TestDescribeSaysWhenThereIsNoAuth(t *testing.T) {
	m, _ := New(Config{Host: "localhost", Port: 25, From: "a@b.c"})
	if got := m.Describe(); !strings.Contains(got, "SMTP_USERNAME is empty") {
		t.Errorf("missing auth not called out:\n%s", got)
	}
}

func TestTheTestMessageIsNotALoginLink(t *testing.T) {
	// A configuration check that dropped a real-looking "sign in" button into
	// an inbox would be indistinguishable from a phishing attempt, and the
	// link would be dead anyway.
	var subject, body string
	m := NewForTesting(func(_ Config, _, s, b string) error {
		subject, body = s, b
		return nil
	})

	if err := m.SendTest("someone@example.com"); err != nil {
		t.Fatal(err)
	}
	if strings.Contains(body, "http://") || strings.Contains(body, "https://") {
		t.Errorf("the test message contains a link:\n%s", body)
	}
	if !strings.Contains(subject, "Проверка") {
		t.Errorf("subject %q does not say it is a check", subject)
	}
	if !strings.Contains(body, "Никаких действий") {
		t.Errorf("the body does not tell the reader to ignore it:\n%s", body)
	}
}

func TestTheLoginLinkCarriesTheLinkAndItsLifetime(t *testing.T) {
	var body string
	m := NewForTesting(func(_ Config, _, _, b string) error {
		body = b
		return nil
	})

	if err := m.SendLoginLink("a@b.c", "https://kairavpn.pro/auth/verify?token=xyz", 15*time.Minute); err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(body, "https://kairavpn.pro/auth/verify?token=xyz") {
		t.Errorf("the link is missing:\n%s", body)
	}
	if !strings.Contains(body, "15 мин") {
		t.Errorf("the expiry is not stated:\n%s", body)
	}
	// Someone who did not ask for this needs to be told nothing has happened,
	// or a stray sign-in email reads as a break-in.
	if !strings.Contains(body, "не запрашивали") {
		t.Errorf("no reassurance for an unrequested link:\n%s", body)
	}
}

func TestNewRefusesAnUnusableConfiguration(t *testing.T) {
	// There is no mock sender to fall back to on purpose: the backend this
	// replaced returned the magic-link token in the API response whenever its
	// mock was active, which meant anyone could claim any address.
	for _, cfg := range []Config{
		{From: "a@b.c"},
		{Host: "smtp.example"},
		{},
	} {
		if _, err := New(cfg); err == nil {
			t.Errorf("New(%+v) succeeded; want an error", cfg)
		}
	}
}

func TestThePortDefaultsToSubmission(t *testing.T) {
	m, err := New(Config{Host: "smtp.example", From: "a@b.c"})
	if err != nil {
		t.Fatal(err)
	}
	if !strings.Contains(m.Describe(), ":587") {
		t.Errorf("default port:\n%s", m.Describe())
	}
}

func TestASendFailureIsReturnedNotSwallowed(t *testing.T) {
	want := errors.New("535 authentication failed")
	m := NewForTesting(func(Config, string, string, string) error { return want })
	if err := m.SendTest("a@b.c"); !errors.Is(err, want) {
		t.Errorf("got %v, want %v", err, want)
	}
}
