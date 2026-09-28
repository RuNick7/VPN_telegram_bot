// Package mailer sends the login links.
//
// There is deliberately no mock or console sender. The backend this replaces
// had exactly one implemented mode -- a mock that printed to stdout -- and
// returned the magic-link token in the API response whenever it was active,
// which meant "email verification" verified nothing: anyone could claim any
// address. A sender that cannot reach a real mailbox must fail, not fall back.
package mailer

import (
	"crypto/tls"
	"crypto/x509"
	"errors"
	"fmt"
	"mime"
	"net"
	"net/smtp"
	"strings"
	"time"
)

type Config struct {
	Host     string
	Port     int
	Username string
	Password string
	From     string
	StartTLS bool
}

type Mailer struct {
	cfg Config
	// send is swapped in tests. Production always uses sendSMTP.
	send func(cfg Config, to, subject, body string) error
	// rootCAs is set only by tests, so Verify can be exercised against a
	// self-signed server. Unexported and never populated by New, so production
	// always validates against the system roots.
	rootCAs *x509.CertPool
}

func New(cfg Config) (*Mailer, error) {
	if cfg.Host == "" || cfg.From == "" {
		return nil, errors.New("mailer: SMTP_HOST and SMTP_FROM are required")
	}
	if cfg.Port == 0 {
		cfg.Port = 587
	}
	return &Mailer{cfg: cfg, send: sendSMTP}, nil
}

// NewForTesting builds a mailer that records instead of sending.
func NewForTesting(send func(cfg Config, to, subject, body string) error) *Mailer {
	return &Mailer{cfg: Config{Host: "test", From: "test@example.com"}, send: send}
}

func (m *Mailer) SendLoginLink(to, link string, ttl time.Duration) error {
	minutes := int(ttl.Minutes())
	body := fmt.Sprintf(
		"Здравствуйте!\n\n"+
			"Чтобы войти в личный кабинет, откройте ссылку:\n\n%s\n\n"+
			"Ссылка действует %d мин. и срабатывает один раз.\n\n"+
			"Если вы не запрашивали вход — просто проигнорируйте это письмо. "+
			"Никаких действий с вашим аккаунтом не произошло.\n",
		link, minutes)
	return m.send(m.cfg, to, "Вход в личный кабинет", body)
}

// SendEmailConfirmation asks somebody to prove they hold an address before it
// becomes a way into their account.
//
// Deliberately worded so that a person who did not ask for it is told plainly
// that nothing has happened: this letter goes to an address typed by whoever
// is driving an account, which is not necessarily its owner. Kept in step with
// send_email_confirmation in shared/tgvpn_shared/mailer.py, which the bot uses
// for the same step.
func (m *Mailer) SendEmailConfirmation(to, link string, bonusDays int, ttl time.Duration) error {
	minutes := int(ttl.Minutes())
	bonus := ""
	if bonusDays > 0 {
		bonus = fmt.Sprintf(" и получить %d дн. подписки", bonusDays)
	}
	body := fmt.Sprintf(
		"Здравствуйте!\n\n"+
			"Этот адрес указали в личном кабинете KairaVPN. Чтобы привязать его к аккаунту%s, "+
			"откройте ссылку:\n\n%s\n\n"+
			"Ссылка действует %d мин. и срабатывает один раз.\n\n"+
			"Если вы этого не делали — просто проигнорируйте письмо. Ничего с вашим адресом "+
			"не произошло, и он ни к чему не привязан.\n",
		bonus, link, minutes)
	return m.send(m.cfg, to, "Подтверждение почты — KairaVPN", body)
}

// SendTest sends a configuration check.
//
// Deliberately not a login link: a test that put a real-looking "sign in"
// button in somebody's inbox would be indistinguishable from the thing an
// attacker sends, and the link would be dead anyway.
func (m *Mailer) SendTest(to string) error {
	body := "Это проверка настроек отправки почты KairaVPN.\n\n" +
		"Если письмо дошло — SMTP настроен верно, и ссылки для входа будут " +
		"приходить тем же путём.\n\n" +
		"Никаких действий не требуется.\n"
	return m.send(m.cfg, to, "Проверка отправки — KairaVPN", body)
}

// Describe reports the settings in use, without the password.
//
// This is printed by the --check-smtp run: the overwhelming majority of mail
// failures are a port paired with the wrong TLS mode or a From on somebody
// else's domain, and both are visible here.
func (m *Mailer) Describe() string {
	tlsMode := "implicit TLS (SMTP_STARTTLS=false)"
	if m.cfg.StartTLS {
		tlsMode = "STARTTLS (SMTP_STARTTLS=true)"
	}
	auth := "none — SMTP_USERNAME is empty"
	if m.cfg.Username != "" {
		auth = fmt.Sprintf("PLAIN as %s, password %d chars", m.cfg.Username, len(m.cfg.Password))
	}
	return fmt.Sprintf("host %s:%d\n  %s\n  auth: %s\n  from: %s",
		m.cfg.Host, m.cfg.Port, tlsMode, auth, m.cfg.From)
}

func (m *Mailer) tlsConfig() *tls.Config {
	return &tls.Config{
		ServerName: m.cfg.Host,
		MinVersion: tls.VersionTLS12,
		RootCAs:    m.rootCAs, // nil in production: use the system roots
	}
}

// Verify opens a connection, negotiates TLS, authenticates and hangs up.
//
// Everything a send does except the send. That is the difference worth having:
// it proves the port is open, that the TLS mode matches it and that the
// credentials are accepted, without putting a message in anybody's inbox --
// so it can be run as often as needed while a hosting provider is still
// opening the port, and it does not spend an allowance or touch a reputation.
func (m *Mailer) Verify() error {
	addr := net.JoinHostPort(m.cfg.Host, fmt.Sprint(m.cfg.Port))

	var client *smtp.Client
	var err error

	if m.cfg.StartTLS {
		conn, dialErr := net.DialTimeout("tcp", addr, 15*time.Second)
		if dialErr != nil {
			return fmt.Errorf("mailer: dial %s: %w", addr, dialErr)
		}
		client, err = smtp.NewClient(conn, m.cfg.Host)
		if err != nil {
			return fmt.Errorf("mailer: smtp handshake: %w", err)
		}
		defer client.Close()
		if ok, _ := client.Extension("STARTTLS"); !ok {
			return errors.New("smtp: server doesn't support STARTTLS")
		}
		if err := client.StartTLS(m.tlsConfig()); err != nil {
			return fmt.Errorf("mailer: starttls: %w", err)
		}
	} else {
		dialer := &net.Dialer{Timeout: 15 * time.Second}
		conn, dialErr := tls.DialWithDialer(dialer, "tcp", addr,
			m.tlsConfig())
		if dialErr != nil {
			return fmt.Errorf("mailer: dial %s: %w", addr, dialErr)
		}
		client, err = smtp.NewClient(conn, m.cfg.Host)
		if err != nil {
			return fmt.Errorf("mailer: smtp handshake: %w", err)
		}
		defer client.Close()
	}

	if m.cfg.Username != "" {
		if err := client.Auth(smtp.PlainAuth("", m.cfg.Username, m.cfg.Password, m.cfg.Host)); err != nil {
			return fmt.Errorf("mailer: auth: %w", err)
		}
	}
	return client.Quit()
}

func sendSMTP(cfg Config, to, subject, body string) error {
	addr := net.JoinHostPort(cfg.Host, fmt.Sprint(cfg.Port))
	message := buildMessage(cfg.From, to, subject, body)

	var auth smtp.Auth
	if cfg.Username != "" {
		auth = smtp.PlainAuth("", cfg.Username, cfg.Password, cfg.Host)
	}

	if cfg.StartTLS {
		// net/smtp negotiates STARTTLS itself inside SendMail when the server
		// advertises it, and refuses to send credentials over a plaintext
		// connection -- which is the behaviour we want.
		return smtp.SendMail(addr, auth, cfg.From, []string{to}, message)
	}

	// Implicit TLS (port 465): the connection is wrapped before any SMTP
	// conversation happens.
	conn, err := tls.Dial("tcp", addr, &tls.Config{ServerName: cfg.Host, MinVersion: tls.VersionTLS12})
	if err != nil {
		return fmt.Errorf("mailer: dial %s: %w", addr, err)
	}
	client, err := smtp.NewClient(conn, cfg.Host)
	if err != nil {
		return fmt.Errorf("mailer: smtp handshake: %w", err)
	}
	defer client.Quit()

	if auth != nil {
		if err := client.Auth(auth); err != nil {
			return fmt.Errorf("mailer: auth: %w", err)
		}
	}
	if err := client.Mail(cfg.From); err != nil {
		return err
	}
	if err := client.Rcpt(to); err != nil {
		return err
	}
	writer, err := client.Data()
	if err != nil {
		return err
	}
	if _, err := writer.Write(message); err != nil {
		return err
	}
	return writer.Close()
}

func buildMessage(from, to, subject, body string) []byte {
	var sb strings.Builder
	sb.WriteString("From: " + from + "\r\n")
	sb.WriteString("To: " + to + "\r\n")
	// Encoded so a non-ASCII subject survives; Russian subjects otherwise
	// arrive as mojibake in several clients.
	sb.WriteString("Subject: " + mime.QEncoding.Encode("utf-8", subject) + "\r\n")
	sb.WriteString("MIME-Version: 1.0\r\n")
	sb.WriteString("Content-Type: text/plain; charset=\"utf-8\"\r\n")
	sb.WriteString("\r\n")
	sb.WriteString(body)
	return []byte(sb.String())
}
