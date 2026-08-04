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
	"net"
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

// untrustedIP reports whether the address we resolved for a request is one
// every visitor would share.
//
// It is, in this deployment: nginx's stream block SNI-routes 443 to the HTTP
// server over loopback without PROXY protocol, so `X-Forwarded-For` is
// literally "127.0.0.1" for everyone. Bucketing on that gave the whole site
// one 20-per-hour allowance between them, and the caller who exhausted it was
// still told the letter had been sent. Nobody could sign in and nothing said
// why.
//
// So a per-IP bucket that cannot distinguish IPs is skipped rather than
// applied to everybody at once. The per-address limit still stands, and it is
// the one that actually protects a mailbox.
func untrustedIP(ip string) bool {
	parsed := net.ParseIP(strings.TrimSpace(ip))
	return parsed == nil || parsed.IsLoopback() || parsed.IsUnspecified()
}

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
	okIP := true
	if !untrustedIP(ip) {
		okIP, err = s.store.AllowAttempt(ctx, "magic-ip:"+ip, magicLinkPerIP, magicLinkWindow)
		if err != nil {
			return err
		}
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

// LoginWithTelegram verifies a login-widget payload and returns a session,
// registering the account if this is a first-time sign-in.
//
// It used to accept only an existing account, which meant "sign in with
// Telegram" worked solely for people who had already opened the bot -- for
// everybody else the button led to "аккаунт не найден, откройте бота". That is
// a dead end on the one route a customer picked precisely because it needs no
// typing.
//
// Registering here is the same trade the magic link already makes. The payload
// is HMAC-signed with the bot's own token and checked for freshness before
// this line, so the identity is proven exactly as an emailed link proves a
// mailbox. It is not an unauthenticated endpoint, whatever the old comment
// here said -- verification happens first, and nothing is created if it fails.
func (s *Service) LoginWithTelegram(ctx context.Context, payload TelegramAuth, ip, userAgent string) (string, *store.User, error) {
	if err := VerifyTelegramAuth(payload, s.telegramToken, time.Now()); err != nil {
		return "", nil, err
	}

	user, err := s.store.UserByTelegramID(ctx, payload.ID)
	if errors.Is(err, store.ErrNotFound) {
		user, err = s.store.CreateTelegramUser(ctx, payload.ID, payload.Username)
	}
	if err != nil {
		return "", nil, err
	}
	session, err := s.NewSession(ctx, user.ID, userAgent, ip)
	return session, user, err
}

// -- binding an address to an account that already exists -------------------

// EmailConfirmTTL is how long a confirmation link stays usable.
//
// Longer than a magic link because the two are answered at different speeds: a
// sign-in link is opened while you are waiting for it, and this one is often
// opened later, on the phone, after the letter has been noticed. Short enough
// that an address typed by mistake stops being bindable the same afternoon.
const EmailConfirmTTL = 30 * time.Minute

// Sending mail to an address the caller names is a spam cannon if it is not
// held down. Per address as well as per account, because one account naming a
// hundred addresses and a hundred accounts naming one are different abuses.
const (
	confirmPerUser  = 5
	confirmPerEmail = 3
	confirmWindow   = time.Hour
)

// RequestEmailConfirmation posts the letter that proves an address.
//
// Nothing is written to the account here. The address only lands on it when
// the link comes back, which is the whole difference from what the bot used to
// do -- it saved whatever was typed, and that address is a sign-in route.
func (s *Service) RequestEmailConfirmation(ctx context.Context, userID, email string, bonusDays int) (string, error) {
	normalized, err := NormalizeEmail(email)
	if err != nil {
		return "", ErrInvalidEmail
	}

	okUser, err := s.store.AllowAttempt(ctx, "confirm-user:"+userID, confirmPerUser, confirmWindow)
	if err != nil {
		return "", err
	}
	okEmail, err := s.store.AllowAttempt(ctx, "confirm-mail:"+normalized, confirmPerEmail, confirmWindow)
	if err != nil {
		return "", err
	}
	if !okUser || !okEmail {
		return "", ErrRateLimited
	}

	token, err := randomToken()
	if err != nil {
		return "", err
	}
	if err := s.store.CreateEmailVerification(ctx, token, userID, normalized, EmailConfirmTTL); err != nil {
		return "", err
	}

	link := s.baseURL + "/auth/confirm-email?token=" + url.QueryEscape(token)
	if err := s.mailer.SendEmailConfirmation(normalized, link, bonusDays, EmailConfirmTTL); err != nil {
		return "", err
	}
	return normalized, nil
}

// ConfirmEmail redeems a confirmation token and reports what it was for.
//
// No session is required, deliberately: the token is the credential and it is
// bound to one account, exactly like a magic link. Requiring a session as well
// would break the ordinary case of opening the letter on a phone that has
// never signed in.
func (s *Service) ConfirmEmail(ctx context.Context, token string) (*store.EmailVerification, error) {
	verification, err := s.store.ConsumeEmailVerification(ctx, token)
	if errors.Is(err, store.ErrNotFound) {
		return nil, ErrBadToken
	}
	return verification, err
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
