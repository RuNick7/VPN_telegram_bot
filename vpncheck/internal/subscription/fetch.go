// Package subscription turns a subscription link into the list of servers to
// check, each with the exact outbound a client app would use to reach it.
package subscription

import (
	"context"
	"crypto/rand"
	"encoding/base64"
	"encoding/hex"
	"fmt"
	"io"
	"net/http"
	"os"
	"path/filepath"
	"runtime"
	"strings"
	"time"
)

// DefaultUserAgent is what the subscription is requested as.
//
// Remnawave answers each client in its own format, chosen by User-Agent. Happ
// is the app every platform's setup instructions point to, and it is answered
// with the Xray JSON template -- the configs customers actually connect with,
// fingerprint and transport settings included. Asking as anything else would
// check a different config from the one that is failing.
const DefaultUserAgent = "Happ/5.5.0"

// maxBody bounds a subscription download. A real one is tens of kilobytes.
const maxBody = 8 << 20

// Fetched is a subscription as the panel returned it.
type Fetched struct {
	URL         string
	Status      int
	ContentType string
	// Title is the profile-title header, which Remnawave base64-encodes.
	Title string
	// UserInfo is subscription-userinfo: traffic and expiry, nothing secret.
	UserInfo string
	// Headers the panel uses to tell a client something, such as the
	// device-limit ones -- what explains a subscription that came back empty.
	Notices map[string]string
	Body    []byte
	Took    time.Duration
}

// Fetch downloads a subscription the way the client app does.
//
// It identifies itself with a device id of its own (see deviceID). A panel
// with device limits switched on hands nothing to a client that sends none,
// and borrowing the id of the customer's real phone is not ours to do. The
// id is stable per computer, so repeated runs count as one device -- which
// shows up in the customer's device list as "vpncheck" and can be removed
// there like any other.
func Fetch(ctx context.Context, client *http.Client, url, userAgent string) (*Fetched, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("User-Agent", userAgent)
	req.Header.Set("Accept", "*/*")
	req.Header.Set("x-hwid", deviceID())
	req.Header.Set("x-device-os", deviceOS())
	req.Header.Set("x-device-model", "vpncheck")

	started := time.Now()
	resp, err := client.Do(req)
	if err != nil {
		return nil, err
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(io.LimitReader(resp.Body, maxBody))
	if err != nil {
		return nil, fmt.Errorf("чтение ответа: %w", err)
	}
	notices := map[string]string{}
	for name, values := range resp.Header {
		lower := strings.ToLower(name)
		if strings.HasPrefix(lower, "x-hwid") || lower == "announce" {
			notices[lower] = decodeTitle(strings.Join(values, ", "))
		}
	}
	return &Fetched{
		Notices:     notices,
		URL:         url,
		Status:      resp.StatusCode,
		ContentType: resp.Header.Get("Content-Type"),
		Title:       decodeTitle(resp.Header.Get("profile-title")),
		UserInfo:    resp.Header.Get("subscription-userinfo"),
		Body:        body,
		Took:        time.Since(started),
	}, nil
}

// decodeTitle undoes the "base64:" prefix Remnawave puts on non-ASCII titles.
func decodeTitle(raw string) string {
	if encoded, ok := strings.CutPrefix(raw, "base64:"); ok {
		if decoded, err := base64.StdEncoding.DecodeString(encoded); err == nil {
			return string(decoded)
		}
	}
	return raw
}

func deviceOS() string {
	switch runtime.GOOS {
	case "darwin":
		return "macOS"
	case "windows":
		return "Windows"
	case "linux":
		return "Linux"
	}
	return runtime.GOOS
}

// deviceID is a random id made on first use and kept in the user's config
// directory, so a computer is one device however many times it runs a check.
// Falls back to a fresh id per run when there is nowhere to keep it.
func deviceID() string {
	dir, err := os.UserConfigDir()
	if err == nil {
		path := filepath.Join(dir, "vpncheck", "hwid")
		if saved, err := os.ReadFile(path); err == nil && len(strings.TrimSpace(string(saved))) >= 16 {
			return strings.TrimSpace(string(saved))
		}
		id := newDeviceID()
		if os.MkdirAll(filepath.Dir(path), 0o700) == nil {
			_ = os.WriteFile(path, []byte(id+"\n"), 0o600)
		}
		return id
	}
	return newDeviceID()
}

func newDeviceID() string {
	raw := make([]byte, 8)
	_, _ = rand.Read(raw)
	return "vpncheck-" + hex.EncodeToString(raw)
}
