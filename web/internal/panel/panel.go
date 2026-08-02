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
	// ErrUsernameTaken means an account with that name is already there. Worth
	// a sentinel of its own because it is recoverable: the caller looks the
	// account up instead of failing, which is what makes two simultaneous
	// first requests -- or a create whose identifier we failed to record --
	// heal rather than wedge.
	ErrUsernameTaken = errors.New("panel: username already exists")
	ErrNotFound      = errors.New("panel: not found")
	ErrUnauthorized  = errors.New("panel: unauthorized")
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

	mu            sync.Mutex
	cachedToken   string
	cachedAt      time.Time
	squadCache    map[string]string
	squadCachedAt time.Time
}

// squadCacheTTL is how long a resolved squad list is reused. Squads are
// created by hand and essentially never change, but a stale entry must not
// outlive an operator renaming one.
const squadCacheTTL = 5 * time.Minute

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

// User is a panel account.
//
// Two generations of the panel identify these differently: older ones give
// every user a `uuid`, newer ones dropped it and address users by a numeric
// `id`. Both fields are decoded and `Ref` picks whichever is present, so one
// client works against either -- which matters because the production panel
// and the one this is tested against are not the same version, and a flag day
// between them is not something a VPN can afford.
type User struct {
	UUID            string      `json:"uuid"`
	ID              json.Number `json:"id"`
	Username        string      `json:"username"`
	SubscriptionURL string      `json:"subscriptionUrl"`
	ExpireAt        string      `json:"expireAt"`
	Status          string      `json:"status"`
	HWIDDeviceLimit *int        `json:"hwidDeviceLimit"`
}

// Ref is how this panel wants the account addressed: in a URL path, and as the
// identifier in a PATCH body. Empty only if the panel returned neither field,
// which means we cannot act on the account at all.
func (u *User) Ref() string {
	if u == nil {
		return ""
	}
	if u.UUID != "" {
		return u.UUID
	}
	return u.ID.String()
}

// numericRef reports whether a ref is a newer panel's numeric id.
//
// A UUID is never all digits, so the two forms cannot be confused. This is
// what lets a ref stored in the database be used later without also having to
// record which generation of panel produced it.
func numericRef(ref string) (int64, bool) {
	n, err := strconv.ParseInt(ref, 10, 64)
	return n, err == nil && ref != ""
}

// identify names an account in a request body the way the panel expects:
// `id` as a number on newer panels, `uuid` as a string on older ones.
func identify(ref string) map[string]any {
	if id, ok := numericRef(ref); ok {
		return map[string]any{"id": id}
	}
	return map[string]any{"uuid": ref}
}

// UserByRef fetches an account by whichever identifier this panel uses.
func (c *Client) UserByRef(ctx context.Context, ref string) (*User, error) {
	if ref == "" {
		return nil, ErrUserNotFound
	}
	raw, err := c.do(ctx, http.MethodGet, "/users/"+url.PathEscape(ref), nil)
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
	if user.Ref() == "" {
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
	if err := json.Unmarshal(raw, &nested); err == nil && nested.User != nil && nested.User.Ref() != "" {
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
func (c *Client) CreateUser(ctx context.Context, username string, telegramID *int64, expireAt time.Time, squadUUIDs []string) (*User, error) {
	payload := map[string]any{
		"username":            username,
		"expireAt":            expireAt.UTC().Format(time.RFC3339),
		"activateAllInbounds": true,
	}
	// Squad membership is what actually grants servers. An account created
	// without one is active, has a subscription link, and reaches nothing --
	// which looks like a working account right up until the customer tries to
	// connect.
	if len(squadUUIDs) > 0 {
		payload["activeInternalSquads"] = squadUUIDs
	}
	if telegramID != nil {
		payload["telegramId"] = *telegramID
	}
	raw, err := c.do(ctx, http.MethodPost, "/users", payload)
	if err != nil {
		if isUsernameTaken(err) {
			return nil, fmt.Errorf("%w: %s", ErrUsernameTaken, username)
		}
		return nil, err
	}
	var user User
	if err := json.Unmarshal(raw, &user); err != nil {
		return nil, fmt.Errorf("panel: decode created user: %w", err)
	}
	return &user, nil
}

// isUsernameTaken recognises the panel's "already exists" refusal.
//
// Matched on the response text because that is all the API offers: a 400 whose
// body carries `errorCode` A019. Both spellings are checked so a version that
// changes one of them still lands here.
func isUsernameTaken(err error) bool {
	text := strings.ToLower(err.Error())
	return strings.Contains(text, "a019") || strings.Contains(text, "already exists")
}

// SetExpiryByRef updates a panel profile's expiry date.
//
// Addressed by the panel's own identifier rather than by name because the two
// kinds of account are named differently -- legacy ones str(telegram_id), new
// ones u-<uuid> -- and patching a name that does not exist updates nothing
// while returning success.
func (c *Client) SetExpiryByRef(ctx context.Context, ref string, expireAt time.Time) error {
	body := identify(ref)
	body["expireAt"] = expireAt.UTC().Format(time.RFC3339)
	_, err := c.do(ctx, http.MethodPatch, "/users", body)
	return err
}

// RevokeSubscription issues a new subscription link and kills the old one.
//
// Sent without a body so the panel generates the new short UUID itself, which
// its own documentation recommends over supplying one. Rotates the link only:
// expiry, traffic counters and squad membership are untouched, and registered
// devices survive -- they simply stop working until the new link is imported.
func (c *Client) RevokeSubscription(ctx context.Context, ref string) (*User, error) {
	raw, err := c.do(ctx, http.MethodPost, "/users/"+url.PathEscape(ref)+"/actions/revoke", nil)
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
func (c *Client) Devices(ctx context.Context, ref string) ([]Device, error) {
	raw, err := c.do(ctx, http.MethodGet, "/hwid/devices/"+url.PathEscape(ref), nil)
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

func (c *Client) DeleteDevice(ctx context.Context, ref, hwid string) error {
	body := map[string]any{"hwid": hwid}
	if id, ok := numericRef(ref); ok {
		body["userId"] = id
	} else {
		body["userUuid"] = ref
	}
	_, err := c.do(ctx, http.MethodPost, "/hwid/devices/delete", body)
	return err
}

// -- squads -----------------------------------------------------------------

type Squad struct {
	UUID string `json:"uuid"`
	Name string `json:"name"`
}

// SquadUUIDByName resolves a configured squad name to the panel's UUID.
//
// Squads kept their `uuid` across the version change that took it away from
// users, so there is only one spelling to handle here. Matched
// case-insensitively, because the name is typed into a .env by a person and
// the panel shows it back with whatever capitalisation it was created with.
//
// Cached for a few minutes: it is read on every account creation and squads
// are made by hand, perhaps once.
func (c *Client) SquadUUIDByName(ctx context.Context, name string) (string, error) {
	wanted := strings.ToLower(strings.TrimSpace(name))
	if wanted == "" {
		return "", errors.New("panel: squad name is empty")
	}

	c.mu.Lock()
	cached, fresh := c.squadCache[wanted], time.Since(c.squadCachedAt) < squadCacheTTL
	c.mu.Unlock()
	if fresh && cached != "" {
		return cached, nil
	}

	raw, err := c.do(ctx, http.MethodGet, "/internal-squads", nil)
	if err != nil {
		return "", err
	}
	var wrapped struct {
		InternalSquads []Squad `json:"internalSquads"`
	}
	squads := wrapped.InternalSquads
	if err := json.Unmarshal(raw, &wrapped); err != nil || wrapped.InternalSquads == nil {
		if err := json.Unmarshal(raw, &squads); err != nil {
			return "", fmt.Errorf("panel: decode squads: %w", err)
		}
	} else {
		squads = wrapped.InternalSquads
	}

	found := ""
	byName := make(map[string]string, len(squads))
	for _, squad := range squads {
		key := strings.ToLower(strings.TrimSpace(squad.Name))
		if squad.UUID != "" {
			byName[key] = squad.UUID
		}
		if key == wanted {
			found = squad.UUID
		}
	}

	c.mu.Lock()
	c.squadCache, c.squadCachedAt = byName, time.Now()
	c.mu.Unlock()

	if found == "" {
		available := make([]string, 0, len(squads))
		for _, squad := range squads {
			available = append(available, squad.Name)
		}
		return "", fmt.Errorf("panel: squad %q not found; the panel has: %s",
			name, strings.Join(available, ", "))
	}
	return found, nil
}
