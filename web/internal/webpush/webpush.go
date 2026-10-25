// Package webpush sends Web Push messages: RFC 8030 delivery, RFC 8291
// payload encryption and RFC 8292 (VAPID) server identification.
//
// Written against the standard library rather than a third-party package
// because the whole protocol is one ECDH, two HKDFs, one AES-GCM seal and one
// ES256 signature, and this module otherwise depends on nothing but pgx.
//
// The endpoint a browser hands us is a URL we will POST to from inside the
// deployment, so it is treated as hostile input: only https, only the push
// services browsers actually use, and redirects are never followed. Without
// that, "subscribe to notifications" is a request-forgery primitive aimed at
// Postgres and the panel.
package webpush

import (
	"bytes"
	"context"
	"crypto/aes"
	"crypto/cipher"
	"crypto/ecdh"
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/hkdf"
	"crypto/rand"
	"crypto/sha256"
	"encoding/base64"
	"encoding/binary"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"strings"
	"time"
)

// Subscription is what PushManager.subscribe() returns, minus the parts we
// do not use.
type Subscription struct {
	Endpoint string
	P256dh   string // the browser's public key, base64url
	Auth     string // the 16-byte authentication secret, base64url
}

// Message is the notification as the service worker receives it.
type Message struct {
	Title string `json:"title"`
	Body  string `json:"body"`
	// URL is a path on this site, opened when the notification is clicked.
	URL string `json:"url"`
	// Tag makes a newer notification replace an older one with the same tag
	// instead of stacking under it.
	Tag string `json:"tag,omitempty"`
}

// ErrGone means the push service no longer knows the subscription: the
// customer revoked permission, cleared the site's data or uninstalled. The
// only correct reaction is to delete it.
var ErrGone = errors.New("push subscription is gone")

// Keys is a VAPID key pair.
type Keys struct {
	private *ecdsa.PrivateKey
	// Public is the uncompressed point, base64url: what the browser is given as
	// applicationServerKey.
	Public string
}

// GenerateKeys makes a fresh VAPID pair, encoded the way the settings store it.
func GenerateKeys() (public, private string, err error) {
	key, err := ecdh.P256().GenerateKey(rand.Reader)
	if err != nil {
		return "", "", err
	}
	return b64(key.PublicKey().Bytes()), b64(key.Bytes()), nil
}

// ParseKeys reads the pair from settings. The public half is derived from the
// private one and must match what was configured: a mismatch would let every
// browser subscribe and every send fail, with nothing to point at the cause.
func ParseKeys(public, private string) (*Keys, error) {
	raw, err := unb64(private)
	if err != nil || len(raw) != 32 {
		return nil, errors.New("WEB_PUSH_VAPID_PRIVATE_KEY is not a base64url P-256 private key")
	}
	key, err := ecdsa.ParseRawPrivateKey(elliptic.P256(), raw)
	if err != nil {
		return nil, fmt.Errorf("WEB_PUSH_VAPID_PRIVATE_KEY: %w", err)
	}
	point, err := key.PublicKey.Bytes()
	if err != nil {
		return nil, err
	}
	if public != "" && strings.TrimRight(strings.TrimSpace(public), "=") != b64(point) {
		return nil, errors.New("WEB_PUSH_VAPID_PUBLIC_KEY does not belong to WEB_PUSH_VAPID_PRIVATE_KEY")
	}
	return &Keys{private: key, Public: b64(point)}, nil
}

// pushHosts are the services browsers subscribe through. Chrome, Edge, Opera,
// Yandex and Samsung all use FCM; Safari uses Apple's; Firefox Mozilla's;
// legacy Edge WNS.
var pushHosts = []string{
	"fcm.googleapis.com",
	".push.apple.com",
	".push.services.mozilla.com",
	".notify.windows.com",
}

// ValidEndpoint reports whether an endpoint is one we are willing to POST to.
func ValidEndpoint(endpoint string) bool {
	if len(endpoint) > 2048 {
		return false
	}
	u, err := url.Parse(endpoint)
	if err != nil || u.Scheme != "https" || u.User != nil || u.Port() != "" {
		return false
	}
	host := strings.ToLower(u.Hostname())
	for _, allowed := range pushHosts {
		if strings.HasPrefix(allowed, ".") {
			if strings.HasSuffix(host, allowed) {
				return true
			}
		} else if host == allowed {
			return true
		}
	}
	return false
}

// Sender delivers messages.
type Sender struct {
	keys    *Keys
	subject string
	client  *http.Client
	now     func() time.Time
	// allow is ValidEndpoint outside tests, which point it at httptest.
	allow func(string) bool
}

// NewSender. `subject` is a mailto: or https: contact the push service may use
// to reach the operator of a misbehaving sender.
func NewSender(keys *Keys, subject string) *Sender {
	return &Sender{
		keys:    keys,
		subject: subject,
		client: &http.Client{
			Timeout: 15 * time.Second,
			CheckRedirect: func(*http.Request, []*http.Request) error {
				return http.ErrUseLastResponse
			},
		},
		now:   time.Now,
		allow: ValidEndpoint,
	}
}

// Send encrypts and delivers one message to one subscription. `ttl` is how
// long the push service should hold it for a device that is offline.
func (s *Sender) Send(ctx context.Context, sub Subscription, msg Message, ttl time.Duration) error {
	if !s.allow(sub.Endpoint) {
		return ErrGone
	}
	payload, err := json.Marshal(msg)
	if err != nil {
		return err
	}
	body, err := encrypt(sub, payload, rand.Reader)
	if err != nil {
		// A key the browser gave us that does not parse will never parse.
		return fmt.Errorf("%w: %v", ErrGone, err)
	}
	auth, err := s.vapid(sub.Endpoint)
	if err != nil {
		return err
	}

	req, err := http.NewRequestWithContext(ctx, http.MethodPost, sub.Endpoint, bytes.NewReader(body))
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", "application/octet-stream")
	req.Header.Set("Content-Encoding", "aes128gcm")
	req.Header.Set("TTL", fmt.Sprint(int(ttl.Seconds())))
	req.Header.Set("Urgency", "normal")
	req.Header.Set("Authorization", auth)

	resp, err := s.client.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	detail, _ := io.ReadAll(io.LimitReader(resp.Body, 512))

	switch {
	case resp.StatusCode >= 200 && resp.StatusCode < 300:
		return nil
	case resp.StatusCode == http.StatusNotFound, resp.StatusCode == http.StatusGone:
		return ErrGone
	default:
		return fmt.Errorf("push service answered %d: %s", resp.StatusCode, strings.TrimSpace(string(detail)))
	}
}

// vapid builds the Authorization header: a short-lived ES256 JWT naming the
// push service's origin, and our public key.
func (s *Sender) vapid(endpoint string) (string, error) {
	u, err := url.Parse(endpoint)
	if err != nil {
		return "", err
	}
	header := b64([]byte(`{"typ":"JWT","alg":"ES256"}`))
	claims, err := json.Marshal(map[string]any{
		"aud": u.Scheme + "://" + u.Host,
		"exp": s.now().Add(12 * time.Hour).Unix(),
		"sub": s.subject,
	})
	if err != nil {
		return "", err
	}
	signingInput := header + "." + b64(claims)
	digest := sha256.Sum256([]byte(signingInput))
	r, ss, err := ecdsa.Sign(rand.Reader, s.keys.private, digest[:])
	if err != nil {
		return "", err
	}
	signature := make([]byte, 64)
	r.FillBytes(signature[:32])
	ss.FillBytes(signature[32:])
	return "vapid t=" + signingInput + "." + b64(signature) + ", k=" + s.keys.Public, nil
}

// recordSize is the aes128gcm record size advertised in the header. A single
// record carries the whole message; notifications are far below it.
const recordSize = 4096

// encrypt implements RFC 8291 over the aes128gcm content coding (RFC 8188).
func encrypt(sub Subscription, plaintext []byte, random io.Reader) ([]byte, error) {
	uaPublicRaw, err := unb64(sub.P256dh)
	if err != nil {
		return nil, errors.New("p256dh is not base64url")
	}
	uaPublic, err := ecdh.P256().NewPublicKey(uaPublicRaw)
	if err != nil {
		return nil, fmt.Errorf("p256dh: %w", err)
	}
	authSecret, err := unb64(sub.Auth)
	if err != nil || len(authSecret) != 16 {
		return nil, errors.New("auth is not a 16-byte base64url secret")
	}
	if len(plaintext)+1+16 > recordSize-86 {
		return nil, errors.New("message too long for one record")
	}

	asPrivate, err := ecdh.P256().GenerateKey(random)
	if err != nil {
		return nil, err
	}
	salt := make([]byte, 16)
	if _, err := io.ReadFull(random, salt); err != nil {
		return nil, err
	}
	return seal(asPrivate, uaPublic, authSecret, salt, plaintext)
}

func seal(asPrivate *ecdh.PrivateKey, uaPublic *ecdh.PublicKey, authSecret, salt, plaintext []byte) ([]byte, error) {
	shared, err := asPrivate.ECDH(uaPublic)
	if err != nil {
		return nil, err
	}
	asPublicRaw := asPrivate.PublicKey().Bytes()
	cek, nonce, err := deriveKeys(shared, authSecret, salt, uaPublic.Bytes(), asPublicRaw)
	if err != nil {
		return nil, err
	}

	block, err := aes.NewCipher(cek)
	if err != nil {
		return nil, err
	}
	gcm, err := cipher.NewGCM(block)
	if err != nil {
		return nil, err
	}
	// 0x02: the padding delimiter of the last (and only) record.
	record := append(append([]byte{}, plaintext...), 0x02)

	out := make([]byte, 0, 16+4+1+len(asPublicRaw)+len(record)+gcm.Overhead())
	out = append(out, salt...)
	out = binary.BigEndian.AppendUint32(out, recordSize)
	out = append(out, byte(len(asPublicRaw)))
	out = append(out, asPublicRaw...)
	return gcm.Seal(out, nonce, record, nil), nil
}

// deriveKeys is the key schedule of RFC 8291 section 3.4, which both ends run.
func deriveKeys(shared, authSecret, salt, uaPublic, asPublic []byte) (cek, nonce []byte, err error) {
	keyInfo := append(append([]byte("WebPush: info\x00"), uaPublic...), asPublic...)
	ikm, err := hkdf.Key(sha256.New, shared, authSecret, string(keyInfo), 32)
	if err != nil {
		return nil, nil, err
	}
	cek, err = hkdf.Key(sha256.New, ikm, salt, "Content-Encoding: aes128gcm\x00", 16)
	if err != nil {
		return nil, nil, err
	}
	nonce, err = hkdf.Key(sha256.New, ikm, salt, "Content-Encoding: nonce\x00", 12)
	return cek, nonce, err
}

func b64(data []byte) string { return base64.RawURLEncoding.EncodeToString(data) }

// unb64 accepts base64url with or without padding: browsers send it bare, and
// a key pasted into .env sometimes picks up `=`.
func unb64(s string) ([]byte, error) {
	return base64.RawURLEncoding.DecodeString(strings.TrimRight(strings.TrimSpace(s), "="))
}
