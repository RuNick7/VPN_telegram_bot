package webpush

import (
	"context"
	"crypto/aes"
	"crypto/cipher"
	"crypto/ecdh"
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/sha256"
	"encoding/binary"
	"encoding/json"
	"errors"
	"io"
	"math/big"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
	"time"
)

// browser plays the user agent: it holds the subscription's private half and
// decrypts what a push service would hand it.
type browser struct {
	key  *ecdh.PrivateKey
	auth []byte
}

func newBrowser(t *testing.T) *browser {
	t.Helper()
	key, err := ecdh.P256().GenerateKey(rand.Reader)
	if err != nil {
		t.Fatal(err)
	}
	auth := make([]byte, 16)
	_, _ = rand.Read(auth)
	return &browser{key: key, auth: auth}
}

func (b *browser) subscription(endpoint string) Subscription {
	return Subscription{Endpoint: endpoint, P256dh: b64(b.key.PublicKey().Bytes()), Auth: b64(b.auth)}
}

// decrypt is RFC 8291 from the receiving side, written from the header layout
// rather than by calling seal, so a mistake shared by both would have to be
// made twice.
func (b *browser) decrypt(t *testing.T, body []byte) []byte {
	t.Helper()
	if len(body) < 21 {
		t.Fatalf("body too short: %d", len(body))
	}
	salt := body[:16]
	if rs := binary.BigEndian.Uint32(body[16:20]); rs != recordSize {
		t.Errorf("record size %d", rs)
	}
	idLen := int(body[20])
	asPublicRaw := body[21 : 21+idLen]
	ciphertext := body[21+idLen:]

	asPublic, err := ecdh.P256().NewPublicKey(asPublicRaw)
	if err != nil {
		t.Fatalf("sender key: %v", err)
	}
	shared, err := b.key.ECDH(asPublic)
	if err != nil {
		t.Fatal(err)
	}
	cek, nonce, err := deriveKeys(shared, b.auth, salt, b.key.PublicKey().Bytes(), asPublicRaw)
	if err != nil {
		t.Fatal(err)
	}
	block, _ := aes.NewCipher(cek)
	gcm, _ := cipher.NewGCM(block)
	plain, err := gcm.Open(nil, nonce, ciphertext, nil)
	if err != nil {
		t.Fatalf("decrypt: %v", err)
	}
	// RFC 8188: the content, a delimiter, then any number of zero bytes.
	end := len(plain) - 1
	for end >= 0 && plain[end] == 0 {
		end--
	}
	if end < 0 || plain[end] != 0x02 {
		t.Fatal("no last-record delimiter")
	}
	return plain[:end]
}

func testKeys(t *testing.T) *Keys {
	t.Helper()
	public, private, err := GenerateKeys()
	if err != nil {
		t.Fatal(err)
	}
	keys, err := ParseKeys(public, private)
	if err != nil {
		t.Fatal(err)
	}
	return keys
}

func TestAMessageDecryptsOnTheBrowserSide(t *testing.T) {
	b := newBrowser(t)
	body, err := encrypt(b.subscription("https://fcm.googleapis.com/fcm/send/x"), []byte(`{"title":"Привет"}`), rand.Reader)
	if err != nil {
		t.Fatal(err)
	}
	if got := string(b.decrypt(t, body)); got != `{"title":"Привет"}` {
		t.Errorf("decrypted %q", got)
	}
}

func TestEveryMessageGetsItsOwnKeyAndSalt(t *testing.T) {
	b := newBrowser(t)
	sub := b.subscription("https://fcm.googleapis.com/fcm/send/x")
	first, _ := encrypt(sub, []byte("same"), rand.Reader)
	second, _ := encrypt(sub, []byte("same"), rand.Reader)
	if string(first[:86]) == string(second[:86]) {
		t.Error("two messages share a salt and sender key")
	}
}

func TestBrokenBrowserKeysAreRefused(t *testing.T) {
	b := newBrowser(t)
	for name, sub := range map[string]Subscription{
		"bad p256dh": {P256dh: "AAAA", Auth: b64(b.auth)},
		"short auth": {P256dh: b64(b.key.PublicKey().Bytes()), Auth: b64(b.auth[:8])},
		"not base64": {P256dh: "%%%", Auth: "%%%"},
	} {
		if _, err := encrypt(sub, []byte("x"), rand.Reader); err == nil {
			t.Errorf("%s: accepted", name)
		}
	}
}

func TestKeysRoundTripAndMismatchIsCaught(t *testing.T) {
	public, private, err := GenerateKeys()
	if err != nil {
		t.Fatal(err)
	}
	keys, err := ParseKeys(public, private)
	if err != nil {
		t.Fatal(err)
	}
	if keys.Public != public {
		t.Errorf("derived public key %q, configured %q", keys.Public, public)
	}
	if _, err := ParseKeys(public+"=", private+"="); err != nil {
		t.Errorf("padding should be tolerated: %v", err)
	}
	otherPublic, _, _ := GenerateKeys()
	if _, err := ParseKeys(otherPublic, private); err == nil {
		t.Error("a public key from another pair was accepted")
	}
	if _, err := ParseKeys("", "short"); err == nil {
		t.Error("a malformed private key was accepted")
	}
}

func TestOnlyRealPushServicesAreEndpoints(t *testing.T) {
	good := []string{
		"https://fcm.googleapis.com/fcm/send/abc",
		"https://web.push.apple.com/QGx",
		"https://updates.push.services.mozilla.com/wpush/v2/x",
		"https://db5p.notify.windows.com/w/?token=x",
	}
	bad := []string{
		"http://fcm.googleapis.com/fcm/send/abc",
		"https://postgres:5432/",
		"https://127.0.0.1/",
		"https://fcm.googleapis.com.evil.example/",
		"https://evilpush.apple.com.example/",
		"https://fcm.googleapis.com:8443/x",
		"https://user@fcm.googleapis.com/x",
		"https://googleapis.com/",
		"https://" + strings.Repeat("a", 2100) + ".push.apple.com/",
		"",
	}
	for _, endpoint := range good {
		if !ValidEndpoint(endpoint) {
			t.Errorf("refused %s", endpoint)
		}
	}
	for _, endpoint := range bad {
		if ValidEndpoint(endpoint) {
			t.Errorf("accepted %.60s", endpoint)
		}
	}
}

func TestSendDeliversWhatThePushServiceExpects(t *testing.T) {
	keys := testKeys(t)
	b := newBrowser(t)

	var got *http.Request
	var body []byte
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		got = r
		body, _ = io.ReadAll(r.Body)
		w.WriteHeader(http.StatusCreated)
	}))
	defer server.Close()

	sender := NewSender(keys, "mailto:ops@example.com")
	sender.allow = func(string) bool { return true }
	msg := Message{Title: "Подписка", Body: "Осталось 3 дня", URL: "/app/plans", Tag: "expiry"}
	if err := sender.Send(context.Background(), b.subscription(server.URL+"/push/1"), msg, time.Hour); err != nil {
		t.Fatal(err)
	}

	if got.Header.Get("Content-Encoding") != "aes128gcm" || got.Header.Get("TTL") != "3600" {
		t.Errorf("headers: %v", got.Header)
	}
	var decoded Message
	if err := json.Unmarshal(b.decrypt(t, body), &decoded); err != nil || decoded != msg {
		t.Errorf("payload %+v, %v", decoded, err)
	}

	// The VAPID token: signed by our key, scoped to the push service's origin.
	auth := got.Header.Get("Authorization")
	token, key, ok := strings.Cut(strings.TrimPrefix(auth, "vapid t="), ", k=")
	if !ok || key != keys.Public {
		t.Fatalf("Authorization %q", auth)
	}
	parts := strings.Split(token, ".")
	if len(parts) != 3 {
		t.Fatalf("token %q", token)
	}
	claimsRaw, _ := unb64(parts[1])
	var claims struct {
		Aud string `json:"aud"`
		Exp int64  `json:"exp"`
		Sub string `json:"sub"`
	}
	_ = json.Unmarshal(claimsRaw, &claims)
	if claims.Aud != server.URL || claims.Sub != "mailto:ops@example.com" {
		t.Errorf("claims %+v", claims)
	}
	if ttl := time.Until(time.Unix(claims.Exp, 0)); ttl <= 0 || ttl > 24*time.Hour {
		t.Errorf("exp is %v away; push services refuse more than 24h", ttl)
	}
	sig, _ := unb64(parts[2])
	point, _ := unb64(keys.Public)
	x, y := elliptic.Unmarshal(elliptic.P256(), point) //nolint:staticcheck
	digest := sha256.Sum256([]byte(parts[0] + "." + parts[1]))
	pub := &ecdsa.PublicKey{Curve: elliptic.P256(), X: x, Y: y}
	if len(sig) != 64 || !ecdsa.Verify(pub, digest[:], new(big.Int).SetBytes(sig[:32]), new(big.Int).SetBytes(sig[32:])) {
		t.Error("VAPID signature does not verify")
	}
}

func TestGoneSubscriptionsAreReportedAsSuch(t *testing.T) {
	for status, wantGone := range map[int]bool{404: true, 410: true, 429: false, 500: false, 301: false} {
		server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
			if status == 301 {
				http.Redirect(w, r, "http://127.0.0.1:1/", status)
				return
			}
			w.WriteHeader(status)
		}))
		sender := NewSender(testKeys(t), "mailto:x@example.com")
		sender.allow = func(string) bool { return true }
		err := sender.Send(context.Background(), newBrowser(t).subscription(server.URL), Message{Title: "x"}, time.Minute)
		server.Close()
		if err == nil {
			t.Errorf("%d: no error", status)
			continue
		}
		if errors.Is(err, ErrGone) != wantGone {
			t.Errorf("%d: gone=%v, want %v (%v)", status, errors.Is(err, ErrGone), wantGone, err)
		}
	}
}

func TestSendRefusesAnEndpointOutsideThePushServices(t *testing.T) {
	sender := NewSender(testKeys(t), "mailto:x@example.com")
	err := sender.Send(context.Background(), newBrowser(t).subscription("https://127.0.0.1/"), Message{}, time.Minute)
	if !errors.Is(err, ErrGone) {
		t.Errorf("err = %v", err)
	}
}
