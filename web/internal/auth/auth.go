// Package auth implements passwordless sign-in: emailed magic links and the
// Telegram login widget.
//
// No password is ever accepted, hashed or stored, so there is no password
// database to leak and no reset flow to abuse.
package auth

import (
	"context"
	"crypto/rand"
	"encoding/base64"
	"errors"
	"net/mail"
	"net/url"
	"strings"
	"time"

	"github.com/RuNick7/VPN_telegram_bot/web/internal/mailer"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/store"
)

var (
	ErrInvalidEmail = errors.New("auth: invalid email address")
	ErrRateLimited  = errors.New("auth: too many attempts")
	ErrBadToken     = errors.New("auth: link is invalid, expired, or already used")
)

// Rate limits. Deliberately tight on a single address -- the cost of a
// mistake here is somebody else's inbox being used as a nuisance channel.
const (
	magicLinkPerEmail   = 5
	magicLinkPerIP      = 20
	magicLinkWindow     = time.Hour
	verifyAttemptsPerIP = 30
	verifyWindow        = 10 * time.Minute
)

type Service struct {
	store         *store.Store
	mailer        *mailer.Mailer
	baseURL       string
	magicTTL      time.Duration
	sessionTTL    time.Duration
	telegramToken string
}

func NewService(st *store.Store, ml *mailer.Mailer, baseURL string, magicTTL, sessionTTL time.Duration, telegramToken string) *Service {
	return &Service{
		store:         st,
		mailer:        ml,
		baseURL:       strings.TrimRight(baseURL, "/"),
		magicTTL:      magicTTL,
		sessionTTL:    sessionTTL,
		telegramToken: telegramToken,
	}
}

// NormalizeEmail validates and lowercases an address.
func NormalizeEmail(raw string) (string, error) {
	trimmed := strings.TrimSpace(raw)
	if trimmed == "" || len(trimmed) > 254 {
		return "", ErrInvalidEmail
	}
	parsed, err := mail.ParseAddress(trimmed)
	if err != nil {
		return "", ErrInvalidEmail
	}
	// ParseAddress accepts `Name <a@b>`; only the address part is the identity.
	return strings.ToLower(parsed.Address), nil
}

// RequestMagicLink emails a single-use sign-in link.
//
// It reports nothing about whether the address is known. Callers return the
// same response either way, so the endpoint cannot be used to enumerate who
// has an account -- which is why the token is created for an *email*, not for
// a user, and the account is only resolved (or created) at redemption time.
func (s *Service) RequestMagicLink(ctx context.Context, email, ip string) error {
	normalized, err := NormalizeEmail(email)
	if err != nil {
		return err
	}

	okEmail, err := s.store.AllowAttempt(ctx, "magic:"+normalized, magicLinkPerEmail, magicLinkWindow)
	if err != nil {
		return err
	}
	okIP, err := s.store.AllowAttempt(ctx, "magic-ip:"+ip, magicLinkPerIP, magicLinkWindow)
	if err != nil {
		return err
	}
	if !okEmail || !okIP {
		return ErrRateLimited
	}

	token, err := randomToken()
	if err != nil {
		return err
	}
	if err := s.store.CreateMagicLink(ctx, token, normalized, s.magicTTL); err != nil {
		return err
	}

	link := s.baseURL + "/auth/verify?token=" + url.QueryEscape(token)
	// The token leaves this process exactly once, into the email. It is never
	// returned to an API caller and never logged.
	return s.mailer.SendLoginLink(normalized, link, s.magicTTL)
}

// RedeemMagicLink turns a link into a session, creating the account if this is
// a first-time sign-in.
//
// Returns the session token and the user it belongs to.
func (s *Service) RedeemMagicLink(ctx context.Context, token, ip, userAgent string) (string, *store.User, error) {
	okIP, err := s.store.AllowAttempt(ctx, "verify-ip:"+ip, verifyAttemptsPerIP, verifyWindow)
	if err != nil {
		return "", nil, err
	}
	if !okIP {
		return "", nil, ErrRateLimited
	}

	email, err := s.store.ConsumeMagicLink(ctx, token)
	if errors.Is(err, store.ErrNotFound) {
		return "", nil, ErrBadToken
	}
	if err != nil {
		return "", nil, err
	}

	user, err := s.store.UserByEmail(ctx, email)
	if errors.Is(err, store.ErrNotFound) {
		// First sign-in from this address: register them. The address is
		// proven at this point -- they opened a link that only its mailbox
		// received -- so this is a verified registration, not a claim.
		user, err = s.store.CreateEmailUser(ctx, email)
	}
	if err != nil {
		return "", nil, err
	}

	session, err := s.NewSession(ctx, user.ID, userAgent, ip)
	return session, user, err
}

// LoginWithTelegram verifies a login-widget payload and returns a session.
//
// Only an existing account is accepted. A Telegram user who has never spoken
// to the bot has no row, and creating one here would mean creating a panel
// profile and a trial from an unauthenticated endpoint -- the bot's /start
// owns that.
func (s *Service) LoginWithTelegram(ctx context.Context, payload TelegramAuth, ip, userAgent string) (string, *store.User, error) {
	if err := VerifyTelegramAuth(payload, s.telegramToken, time.Now()); err != nil {
		return "", nil, err
	}

	user, err := s.store.UserByTelegramID(ctx, payload.ID)
	if err != nil {
		return "", nil, err
	}
	session, err := s.NewSession(ctx, user.ID, userAgent, ip)
	return session, user, err
}

func (s *Service) NewSession(ctx context.Context, userID, userAgent, ip string) (string, error) {
	token, err := randomToken()
	if err != nil {
		return "", err
	}
	if err := s.store.CreateSession(ctx, token, userID, s.sessionTTL, userAgent, ip); err != nil {
		return "", err
	}
	return token, nil
}

func (s *Service) UserForSession(ctx context.Context, token string) (*store.User, error) {
	return s.store.SessionUser(ctx, token)
}

func (s *Service) EndSession(ctx context.Context, token string) error {
	return s.store.DeleteSession(ctx, token)
}

func (s *Service) SessionTTL() time.Duration { return s.sessionTTL }

// randomToken returns 256 bits of entropy, URL-safe.
//
// crypto/rand, not math/rand: this value is the credential.
func randomToken() (string, error) {
	buf := make([]byte, 32)
	if _, err := rand.Read(buf); err != nil {
		return "", err
	}
	return base64.RawURLEncoding.EncodeToString(buf), nil
}
