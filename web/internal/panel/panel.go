// Package panel is a deliberately narrow Remnawave client: only the endpoints
// the website actually needs.
//
// It is not a second SDK. The bots keep the full Python client; this one
// covers user lookup, subscription-link rotation and device management, and
// nothing else. Anything it does not implement, the site does not do.
package panel

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strconv"
	"strings"
	"sync"
	"time"
)

var (
	ErrUserNotFound = errors.New("panel: user not found")
	ErrNotFound     = errors.New("panel: not found")
	ErrUnauthorized = errors.New("panel: unauthorized")
)

// tokenTTL caps how long a login-issued token is reused before
// re-authenticating. Matches the Python client.
const tokenTTL = 15 * time.Minute

type Client struct {
	baseURL  string
	token    string // static token, when configured
	username string
	password string
	http     *http.Client

	mu          sync.Mutex
	cachedToken string
	cachedAt    time.Time
}

func New(baseURL, token, username, password string, timeout time.Duration) (*Client, error) {
	normalized, err := NormalizeBaseURL(baseURL)
	if err != nil {
		return nil, err
	}
	if token == "" && (username == "" || password == "") {
		return nil, errors.New("panel: need a token or username+password")
	}
	if timeout <= 0 {
		timeout = 10 * time.Second
	}
	return &Client{
		baseURL:  normalized,
		token:    normalizeToken(token),
		username: username,
		password: password,
		http:     &http.Client{Timeout: timeout},
	}, nil
}

// NormalizeBaseURL turns whatever is in REMNAWAVE_BASE_URL into `<origin>/api`.
//
// Accepts values with or without a scheme and with or without a trailing
// `/api`; both spellings appear in real .env files. Parsing happens before
// trimming because stripping slashes off a bare "https://" first would leave
// "https:", which then parses as a hostname.
func NormalizeBaseURL(raw string) (string, error) {
	raw = strings.TrimSpace(raw)
	if raw == "" {
		return "", errors.New("panel: REMNAWAVE_BASE_URL is empty")
	}
	if !strings.HasPrefix(raw, "http://") && !strings.HasPrefix(raw, "https://") {
		raw = "https://" + raw
	}
	parsed, err := url.Parse(raw)
	if err != nil || parsed.Host == "" {
		return "", fmt.Errorf("panel: invalid REMNAWAVE_BASE_URL: %s", raw)
	}
	path := strings.TrimRight(parsed.Path, "/")
	path = strings.TrimSuffix(path, "/api")
	return fmt.Sprintf("%s://%s%s/api", parsed.Scheme, parsed.Host, path), nil
}

// normalizeToken strips an accidental "Bearer " prefix; people paste it in
// from the docs.
func normalizeToken(raw string) string {
	raw = strings.TrimSpace(raw)
	if len(raw) > 7 && strings.EqualFold(raw[:7], "bearer ") {
		return strings.TrimSpace(raw[7:])
	}
	return raw
}

// UsernameFor is the panel name for an account we are creating now.
//
// Derived from our own UUID, never from a Telegram ID, so an account can exist
// -- and be paid for -- with no Telegram at all. Must stay identical to
// `panel_username_for` in shared/tgvpn_shared/identity.py: the bot and the
// site create accounts for the same people and must not produce two names.
func UsernameFor(userID string) string {
	compact := strings.ReplaceAll(userID, "-", "")
	if len(compact) > 16 {
		compact = compact[:16]
	}
	return "u-" + compact
}

// LegacyUsername is what an account created before the identity rework is
// called in the panel. Those are deliberately never renamed.
func LegacyUsername(telegramID *int64) string {
	if telegramID == nil {
		return ""
	}
	return strconv.FormatInt(*telegramID, 10)
}

// -- transport --------------------------------------------------------------

func (c *Client) authToken(ctx context.Context) (string, error) {
	if c.token != "" {
		return c.token, nil
	}
	c.mu.Lock()
	defer c.mu.Unlock()
	if c.cachedToken != "" && time.Since(c.cachedAt) < tokenTTL {
		return c.cachedToken, nil
	}
	return c.loginLocked(ctx)
}

func (c *Client) loginLocked(ctx context.Context) (string, error) {
	body, _ := json.Marshal(map[string]string{"username": c.username, "password": c.password})
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.baseURL+"/auth/login", bytes.NewReader(body))
	if err != nil {
		return "", err
	}
	req.Header.Set("Content-Type", "application/json")

	resp, err := c.http.Do(req)
	if err != nil {
		return "", fmt.Errorf("panel: login: %w", err)
	}
	defer resp.Body.Close()
	if resp.StatusCode >= 400 {
		return "", fmt.Errorf("panel: login failed with %d", resp.StatusCode)
	}

	var parsed struct {
		Response struct {
			AccessToken string `json:"accessToken"`
		} `json:"response"`
		AccessToken string `json:"accessToken"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&parsed); err != nil {
		return "", fmt.Errorf("panel: decode login: %w", err)
	}
	token := parsed.Response.AccessToken
	if token == "" {
		token = parsed.AccessToken
	}
	if token == "" {
		return "", errors.New("panel: login returned no accessToken")
	}
	c.cachedToken, c.cachedAt = token, time.Now()
	return token, nil
}

// do issues an authenticated request, retrying once if a login-issued token is
// rejected. A 401 against a *static* token is a configuration problem and
// surfaces rather than looping.
func (c *Client) do(ctx context.Context, method, path string, payload any) (json.RawMessage, error) {
	token, err := c.authToken(ctx)
	if err != nil {
		return nil, err
	}
	raw, err := c.send(ctx, method, path, token, payload)
	if !errors.Is(err, ErrUnauthorized) || c.token != "" {
		return raw, err
	}

	c.mu.Lock()
	c.cachedToken = ""
	fresh, loginErr := c.loginLocked(ctx)
	c.mu.Unlock()
	if loginErr != nil {
		return nil, loginErr
	}
	return c.send(ctx, method, path, fresh, payload)
}

func (c *Client) send(ctx context.Context, method, path, token string, payload any) (json.RawMessage, error) {
	var body io.Reader
	if payload != nil {
		encoded, err := json.Marshal(payload)
		if err != nil {
			return nil, err
		}
		body = bytes.NewReader(encoded)
	}

	req, err := http.NewRequestWithContext(ctx, method, c.baseURL+path, body)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", "Bearer "+token)
	if payload != nil {
		req.Header.Set("Content-Type", "application/json")
	}

	resp, err := c.http.Do(req)
	if err != nil {
		return nil, fmt.Errorf("panel: %s %s: %w", method, path, err)
	}
	defer resp.Body.Close()

	switch {
	case resp.StatusCode == http.StatusUnauthorized:
		return nil, ErrUnauthorized
	case resp.StatusCode == http.StatusNotFound:
		return nil, ErrNotFound
	case resp.StatusCode >= 400:
		snippet, _ := io.ReadAll(io.LimitReader(resp.Body, 512))
		return nil, fmt.Errorf("panel: %s %s returned %d: %s", method, path, resp.StatusCode, snippet)
	}

	raw, err := io.ReadAll(resp.Body)
	if err != nil {
		return nil, err
	}
	return unwrap(raw), nil
}

// unwrap returns a payload's `response` envelope, or the payload itself.
// The panel wraps most successful bodies but not every endpoint in every
// version does.
func unwrap(raw []byte) json.RawMessage {
	if len(raw) == 0 {
		return json.RawMessage("null")
	}
	var envelope struct {
		Response json.RawMessage `json:"response"`
	}
	if err := json.Unmarshal(raw, &envelope); err == nil && len(envelope.Response) > 0 {
		return envelope.Response
	}
	return raw
}

// -- users ------------------------------------------------------------------

type User struct {
	UUID            string `json:"uuid"`
	Username        string `json:"username"`
	SubscriptionURL string `json:"subscriptionUrl"`
	ExpireAt        string `json:"expireAt"`
	Status          string `json:"status"`
	HWIDDeviceLimit *int   `json:"hwidDeviceLimit"`
}

func (c *Client) UserByUUID(ctx context.Context, userUUID string) (*User, error) {
	raw, err := c.do(ctx, http.MethodGet, "/users/"+url.PathEscape(userUUID), nil)
	if errors.Is(err, ErrNotFound) {
		return nil, ErrUserNotFound
	}
	if err != nil {
		return nil, err
	}
	var user User
	if err := json.Unmarshal(raw, &user); err != nil {
		return nil, fmt.Errorf("panel: decode user: %w", err)
	}
	if user.UUID == "" {
		return nil, ErrUserNotFound
	}
	return &user, nil
}

func (c *Client) UserByUsername(ctx context.Context, username string) (*User, error) {
	raw, err := c.do(ctx, http.MethodGet, "/users/by-username/"+url.PathEscape(username), nil)
	if errors.Is(err, ErrNotFound) {
		return nil, ErrUserNotFound
	}
	if err != nil {
		return nil, err
	}
	// Some panel versions nest the user under `response.user`, others return
	// its fields directly.
	var nested struct {
		User *User `json:"user"`
	}
	if err := json.Unmarshal(raw, &nested); err == nil && nested.User != nil && nested.User.UUID != "" {
		return nested.User, nil
	}
	var user User
	if err := json.Unmarshal(raw, &user); err != nil {
		return nil, fmt.Errorf("panel: decode user: %w", err)
	}
	if user.UUID == "" {
		return nil, ErrUserNotFound
	}
	return &user, nil
}

// CreateUser registers a panel profile.
//
// `expireAt` is passed in rather than derived so the caller owns the policy:
// the site creates web-native accounts already expired, because granting a
// trial per email address would be a trial per mailbox.
func (c *Client) CreateUser(ctx context.Context, username string, telegramID *int64, expireAt time.Time) (*User, error) {
	payload := map[string]any{
		"username":            username,
		"expireAt":            expireAt.UTC().Format(time.RFC3339),
		"activateAllInbounds": true,
	}
	if telegramID != nil {
		payload["telegramId"] = *telegramID
	}
	raw, err := c.do(ctx, http.MethodPost, "/users", payload)
	if err != nil {
		return nil, err
	}
	var user User
	if err := json.Unmarshal(raw, &user); err != nil {
		return nil, fmt.Errorf("panel: decode created user: %w", err)
	}
	return &user, nil
}

// SetExpiryByUUID updates a panel profile's expiry date.
//
// Addressed by UUID rather than by name because the two kinds of account are
// named differently -- legacy ones str(telegram_id), new ones u-<uuid> -- and
// patching a name that does not exist updates nothing while returning success.
func (c *Client) SetExpiryByUUID(ctx context.Context, userUUID string, expireAt time.Time) error {
	_, err := c.do(ctx, http.MethodPatch, "/users", map[string]any{
		"uuid":     userUUID,
		"expireAt": expireAt.UTC().Format(time.RFC3339),
	})
	return err
}

// RevokeSubscription issues a new subscription link and kills the old one.
//
// Sent without a body so the panel generates the new short UUID itself, which
// its own documentation recommends over supplying one. Rotates the link only:
// expiry, traffic counters and squad membership are untouched, and registered
// devices survive -- they simply stop working until the new link is imported.
func (c *Client) RevokeSubscription(ctx context.Context, userUUID string) (*User, error) {
	raw, err := c.do(ctx, http.MethodPost, "/users/"+url.PathEscape(userUUID)+"/actions/revoke", nil)
	if err != nil {
		return nil, err
	}
	var user User
	if err := json.Unmarshal(raw, &user); err != nil {
		return nil, fmt.Errorf("panel: decode revoked user: %w", err)
	}
	return &user, nil
}

// -- devices ----------------------------------------------------------------

type Device struct {
	HWID        string `json:"hwid"`
	Platform    string `json:"platform"`
	OSVersion   string `json:"osVersion"`
	DeviceModel string `json:"deviceModel"`
	UserAgent   string `json:"userAgent"`
	CreatedAt   string `json:"createdAt"`
	UpdatedAt   string `json:"updatedAt"`
}

// Devices lists what is registered against a user.
//
// A 404 reads as "none": panels with HWID tracking switched off answer that
// way, and an empty list is the honest thing to show for them. DeleteDevice
// below is strict for the mirror-image reason -- there a silent no-op would
// tell a user their device was removed when it was not.
func (c *Client) Devices(ctx context.Context, userUUID string) ([]Device, error) {
	raw, err := c.do(ctx, http.MethodGet, "/hwid/devices/"+url.PathEscape(userUUID), nil)
	if errors.Is(err, ErrNotFound) {
		return nil, nil
	}
	if err != nil {
		return nil, err
	}
	var wrapped struct {
		Devices []Device `json:"devices"`
	}
	if err := json.Unmarshal(raw, &wrapped); err == nil && wrapped.Devices != nil {
		return wrapped.Devices, nil
	}
	var devices []Device
	if err := json.Unmarshal(raw, &devices); err != nil {
		return nil, fmt.Errorf("panel: decode devices: %w", err)
	}
	return devices, nil
}

func (c *Client) DeleteDevice(ctx context.Context, userUUID, hwid string) error {
	_, err := c.do(ctx, http.MethodPost, "/hwid/devices/delete", map[string]string{
		"userUuid": userUUID,
		"hwid":     hwid,
	})
	return err
}
