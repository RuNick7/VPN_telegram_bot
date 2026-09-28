package main

import (
	"errors"
	"net"
	"strings"
	"testing"

	"github.com/RuNick7/VPN_telegram_bot/web/internal/config"
)

// The point of `diagnose` is that an operator reads its output instead of a
// bare "535 5.7.8". These check that each failure lands on the setting that
// actually has to change.
func TestDiagnosePointsAtTheSettingToChange(t *testing.T) {
	cases := []struct {
		name string
		err  error
		cfg  config.SMTP
		want string // a phrase that must appear
	}{
		{
			name: "blocked port",
			err:  errors.New("dial tcp 1.2.3.4:587: i/o timeout"),
			cfg:  config.SMTP{Host: "smtp.go1.unisender.ru", Port: 587, StartTLS: true},
			want: "nc -zv smtp.go1.unisender.ru 587",
		},
		{
			name: "wrong tls mode for the port",
			err:  errors.New("tls: first record does not look like a TLS handshake"),
			cfg:  config.SMTP{Host: "smtp.example", Port: 587, StartTLS: false},
			want: "SMTP_STARTTLS=true with port 587",
		},
		{
			name: "wrong tls mode the other way",
			err:  errors.New("x509: certificate signed by unknown authority"),
			cfg:  config.SMTP{Host: "smtp.example", Port: 465, StartTLS: true},
			want: "SMTP_STARTTLS=false with port 465",
		},
		{
			name: "bad key",
			err:  errors.New("535 5.7.8 Error: authentication failed"),
			cfg:  config.SMTP{Host: "smtp.go1.unisender.ru", Port: 587, StartTLS: true},
			want: "the SMTP password is",
		},
		{
			name: "unverified sending domain",
			err:  errors.New("550 5.7.1 Sender address rejected: domain not verified"),
			cfg:  config.SMTP{From: "noreply@kairavpn.pro"},
			want: `refused the sender "noreply@kairavpn.pro"`,
		},
		{
			name: "no starttls offered",
			err:  errors.New("smtp: server doesn't support STARTTLS"),
			cfg:  config.SMTP{Port: 25, StartTLS: true},
			want: "SMTP_STARTTLS=false and use port 465",
		},
		{
			name: "connection refused",
			err:  errors.New("dial tcp 1.2.3.4:465: connect: connection refused"),
			cfg:  config.SMTP{Host: "smtp.example", Port: 465},
			want: "Nothing is listening on smtp.example:465",
		},
	}

	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			got := diagnose(tc.err, tc.cfg)
			if !strings.Contains(got, tc.want) {
				t.Errorf("diagnose(%v):\n%s\n\nwant it to contain %q", tc.err, got, tc.want)
			}
		})
	}
}

func TestDiagnoseRecognisesADNSFailure(t *testing.T) {
	// A typo in SMTP_HOST is the cheapest possible mistake and arrives wrapped
	// in a *net.DNSError, not as a string worth matching on.
	err := &net.DNSError{Err: "no such host", Name: "smtp.gо1.unisender.ru", IsNotFound: true}
	if got := diagnose(err, config.SMTP{}); !strings.Contains(got, "SMTP_HOST") {
		t.Errorf("got %q, want it to mention SMTP_HOST", got)
	}
}

func TestDiagnoseAlwaysSaysSomething(t *testing.T) {
	got := diagnose(errors.New("452 4.3.1 insufficient system storage"), config.SMTP{})
	if strings.TrimSpace(got) == "" {
		t.Error("an unrecognised error produced no guidance at all")
	}
}
