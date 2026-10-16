// Package redact keeps secrets out of everything vpncheck writes.
//
// Logs leave the machine: an operator pastes them into a chat, a customer
// sends them to support. What must not go with them is anything that lets
// somebody else connect as this user -- the user's id, passwords, the
// subscription link -- or that a server's keys would give away.
//
// A secret is replaced by a marker derived from it with a per-run salt, so
// within one report the same key still reads as the same key ("these two
// hosts share a shortId") while nothing about it survives across reports.
package redact

import (
	"crypto/rand"
	"crypto/sha256"
	"encoding/hex"
	"net/url"
	"regexp"
	"sort"
	"strings"
	"sync"
	"unicode"
)

// Too short to be a secret worth hiding, and short enough to collide with
// ordinary text: a two-character shortId replaced everywhere would shred
// the log it appears in.
const minSecretLen = 6

// secretKeys are the JSON keys whose values are credentials in an Xray
// config: user ids, passwords, REALITY and WireGuard keys, VLESS
// encryption parameters (which embed keys), and the email a panel may put on
// a user (which names a person).
var secretKeys = map[string]bool{
	"id": true, "uuid": true, "password": true, "pass": true, "auth": true,
	"publicKey": true, "shortId": true, "shortIds": true, "privateKey": true,
	"mldsa65Verify": true, "mldsa65Seed": true, "secretKey": true, "preSharedKey": true,
	"seed": true, "encryption": true, "email": true, "user": true,
}

var uuidPattern = regexp.MustCompile(`(?i)\b[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\b`)

// localAddr is the near side of a connection as Go prints it in an error,
// "read tcp 192.0.2.10:51234->203.0.113.5:443". Behind NAT it is a private
// address; on IPv6 it is often the computer's own public one.
var localAddr = regexp.MustCompile(`\b((?:tcp|udp)[46]? )(?:\[[0-9a-fA-F:.%\w]+\]|[0-9a-fA-F:.]+):\d+->`)

type Redactor struct {
	mu       sync.Mutex
	salt     []byte
	secrets  map[string]string
	replacer *strings.Replacer
}

func New() *Redactor {
	salt := make([]byte, 16)
	_, _ = rand.Read(salt)
	return &Redactor{salt: salt, secrets: map[string]string{}}
}

func (r *Redactor) marker(secret string) string {
	// A UUID is the same id in either case, and logs are not consistent
	// about which they print.
	if len(secret) == 36 && uuidPattern.MatchString(secret) {
		secret = strings.ToLower(secret)
	}
	sum := sha256.Sum256(append(append([]byte{}, r.salt...), secret...))
	return "[скрыто:" + hex.EncodeToString(sum[:3]) + "]"
}

// Add registers one secret value.
func (r *Redactor) Add(secret string) {
	r.addAs(secret, "")
}

func (r *Redactor) addAs(secret, marker string) {
	secret = strings.TrimSpace(secret)
	if len(secret) < minSecretLen || secret == "none" {
		return
	}
	r.mu.Lock()
	defer r.mu.Unlock()
	if _, ok := r.secrets[secret]; ok {
		return
	}
	if marker == "" {
		marker = r.marker(secret)
	}
	r.secrets[secret] = marker
	r.replacer = nil
}

// AddURL registers a subscription link: the whole of it, and the parts of
// it that work as a token on their own -- the panel identifies the user by
// the last path segment, and that alone is enough to fetch everything.
func (r *Redactor) AddURL(raw string) {
	r.addAs(raw, "[ссылка подписки]")
	u, err := url.Parse(raw)
	if err != nil {
		return
	}
	for _, segment := range strings.Split(u.Path, "/") {
		if looksLikeToken(segment) {
			r.Add(segment)
		}
	}
	for _, values := range u.Query() {
		for _, value := range values {
			r.Add(value)
		}
	}
}

// looksLikeToken tells a generated identifier from a word in a path such as
// "sub" or "subscription".
func looksLikeToken(segment string) bool {
	if len(segment) < 8 {
		return false
	}
	var digit, upper, lower bool
	for _, c := range segment {
		switch {
		case unicode.IsDigit(c):
			digit = true
		case unicode.IsUpper(c):
			upper = true
		case unicode.IsLower(c):
			lower = true
		}
	}
	return digit || (upper && lower)
}

// AddConfig registers every credential found anywhere in a decoded JSON value.
func (r *Redactor) AddConfig(value any) {
	switch v := value.(type) {
	case map[string]any:
		for key, item := range v {
			if secretKeys[key] {
				r.addValue(item)
				continue
			}
			r.AddConfig(item)
		}
	case []any:
		for _, item := range v {
			r.AddConfig(item)
		}
	}
}

func (r *Redactor) addValue(value any) {
	switch v := value.(type) {
	case string:
		r.Add(v)
	case []any:
		for _, item := range v {
			r.addValue(item)
		}
	}
}

// Config returns a copy of a decoded JSON value with every credential
// replaced, for writing a config down.
func (r *Redactor) Config(value any) any {
	switch v := value.(type) {
	case map[string]any:
		out := make(map[string]any, len(v))
		for key, item := range v {
			if secretKeys[key] {
				out[key] = r.maskValue(item)
				continue
			}
			out[key] = r.Config(item)
		}
		return out
	case []any:
		out := make([]any, len(v))
		for i, item := range v {
			out[i] = r.Config(item)
		}
		return out
	case string:
		return r.String(v)
	}
	return value
}

func (r *Redactor) maskValue(value any) any {
	switch v := value.(type) {
	case string:
		if len(strings.TrimSpace(v)) < minSecretLen || v == "none" {
			return v
		}
		r.Add(v)
		return r.marker(strings.TrimSpace(v))
	case []any:
		out := make([]any, len(v))
		for i, item := range v {
			out[i] = r.maskValue(item)
		}
		return out
	}
	return value
}

// String replaces every registered secret, and anything shaped like a UUID,
// in a piece of text.
func (r *Redactor) String(text string) string {
	r.mu.Lock()
	if r.replacer == nil && len(r.secrets) > 0 {
		// Longest first, so a secret that contains another is replaced whole.
		keys := make([]string, 0, len(r.secrets))
		for secret := range r.secrets {
			keys = append(keys, secret)
		}
		sort.Slice(keys, func(i, j int) bool { return len(keys[i]) > len(keys[j]) })
		pairs := make([]string, 0, 2*len(keys))
		for _, secret := range keys {
			pairs = append(pairs, secret, r.secrets[secret])
		}
		r.replacer = strings.NewReplacer(pairs...)
	}
	replacer := r.replacer
	r.mu.Unlock()

	if replacer != nil {
		text = replacer.Replace(text)
	}
	text = localAddr.ReplaceAllString(text, "${1}[мой адрес]->")
	return uuidPattern.ReplaceAllStringFunc(text, r.marker)
}
