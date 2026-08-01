package main

import (
	"errors"
	"fmt"
	"net"
	"strings"

	"github.com/RuNick7/VPN_telegram_bot/web/internal/config"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/mailer"
)

// checkSMTP sends one test message and explains whatever went wrong.
//
// It exists because the server's own startup check only asserts that
// SMTP_HOST and SMTP_FROM are non-empty. Everything that actually decides
// whether mail arrives -- a port paired with the wrong TLS mode, a key pasted
// with a stray space, a sending domain the provider has not verified, an
// outbound port the hosting company blocks -- shows up only when a customer
// does not receive their login link, and a customer who does not receive it
// cannot get into their account at all. Better to find out here.
//
// Nothing else is started: no database connection, no panel client, no
// listener. That way it is usable before the rest of the deployment exists.
func checkSMTP(recipient string) error {
	// Validation errors are reported but not fatal: DATABASE_URL and the panel
	// credentials have nothing to do with sending mail, and someone testing
	// SMTP early may not have set them yet.
	cfg, cfgErr := config.Load(".env", "../.env")
	if cfgErr != nil && !cfg.SMTP.Configured() {
		return fmt.Errorf("%w", cfgErr)
	}
	if cfgErr != nil {
		fmt.Printf("note: other settings are incomplete, ignoring for this check:\n  %v\n\n", cfgErr)
	}

	ml, err := mailer.New(mailer.Config{
		Host:     cfg.SMTP.Host,
		Port:     cfg.SMTP.Port,
		Username: cfg.SMTP.Username,
		Password: cfg.SMTP.Password,
		From:     cfg.SMTP.From,
		StartTLS: cfg.SMTP.StartTLS,
	})
	if err != nil {
		return err
	}

	fmt.Printf("Sending a test message.\n  %s\n  to: %s\n\n", ml.Describe(), recipient)

	if err := ml.SendTest(recipient); err != nil {
		fmt.Printf("FAILED\n\n%v\n\n%s\n", err, diagnose(err, cfg.SMTP))
		return errors.New("smtp check failed")
	}

	fmt.Printf("Accepted by the server.\n\n" +
		"That means it was handed over, not that it landed in an inbox. Check the\n" +
		"recipient, including spam, and check the provider's own delivery log.\n" +
		"If it went to spam, the DNS records are what to fix: SPF, DKIM, DMARC.\n")
	return nil
}

// diagnose turns an SMTP failure into the thing to go and change.
//
// Matching on message text is crude, but net/smtp surfaces server replies as
// plain strings and the alternative is handing the operator a bare 535.
func diagnose(err error, smtpCfg config.SMTP) string {
	text := strings.ToLower(err.Error())

	var dnsErr *net.DNSError
	if errors.As(err, &dnsErr) {
		return "The hostname did not resolve. Check SMTP_HOST for a typo."
	}

	switch {
	case strings.Contains(text, "timeout"), strings.Contains(text, "i/o timeout"):
		return fmt.Sprintf(
			"The connection timed out. Most often this is the hosting provider blocking\n"+
				"outbound mail ports. Test it directly:\n\n    nc -zv %s %d\n\n"+
				"If that hangs too, ask them to open the port.", smtpCfg.Host, smtpCfg.Port)

	case strings.Contains(text, "connection refused"):
		return fmt.Sprintf(
			"Nothing is listening on %s:%d. Check the port against the provider's docs:\n"+
				"587 and 2525 want SMTP_STARTTLS=true, 465 wants SMTP_STARTTLS=false.",
			smtpCfg.Host, smtpCfg.Port)

	// Ahead of the general TLS case: "STARTTLS" contains "tls", and this one
	// has a specific answer rather than "the port and the mode disagree".
	case strings.Contains(text, "starttls"):
		return "The server did not offer STARTTLS, so Go refused to send credentials over a\n" +
			"plaintext connection. Set SMTP_STARTTLS=false and use port 465."

	case strings.Contains(text, "tls"), strings.Contains(text, "x509"),
		strings.Contains(text, "handshake"), strings.Contains(text, "first record"):
		other := "SMTP_STARTTLS=false with port 465"
		if !smtpCfg.StartTLS {
			other = "SMTP_STARTTLS=true with port 587"
		}
		return fmt.Sprintf(
			"TLS failed. The port and the TLS mode almost certainly disagree — right now\n"+
				"this is port %d with SMTP_STARTTLS=%t. Try %s.",
			smtpCfg.Port, smtpCfg.StartTLS, other)

	case strings.Contains(text, "535"), strings.Contains(text, "authentication"),
		strings.Contains(text, "auth"), strings.Contains(text, "credentials"):
		return "The server rejected the credentials. For Unisender Go the SMTP password is\n" +
			"the API key, and the username is the SMTP login from the account — not the\n" +
			"address in SMTP_FROM. Check for a trailing space in the key.\n" +
			"For Yandex it must be an app password, not the account password."

	case strings.Contains(text, "550"), strings.Contains(text, "553"),
		strings.Contains(text, "sender"), strings.Contains(text, "domain"),
		strings.Contains(text, "not allowed"), strings.Contains(text, "unverified"):
		return fmt.Sprintf(
			"The server refused the sender %q. Providers only accept a From on a domain\n"+
				"you have added and verified in their panel, with their DKIM and SPF records\n"+
				"live in DNS. Verify the domain first, then run this again.", smtpCfg.From)
	}

	return "Check the settings above against the provider's SMTP documentation."
}
