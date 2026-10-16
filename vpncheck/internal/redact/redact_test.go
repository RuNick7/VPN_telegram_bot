package redact

import (
	"encoding/json"
	"strings"
	"testing"
)

const config = `{
  "outbounds": [{
    "protocol": "vless",
    "settings": {"vnext": [{"address": "de1.example.net", "port": 443,
      "users": [{"id": "B831381D-6324-4D53-AD4F-8CDA48B30811", "flow": "xtls-rprx-vision", "encryption": "none", "email": "u-0123456789abcdef"}]}]},
    "streamSettings": {"security": "reality", "realitySettings": {
      "serverName": "www.example.com", "publicKey": "7xhH4b_VkliBxGulljcyPOH-bYUA2dl-XAdZAsfhk04",
      "shortId": "6ba85179e30d4fc2", "fingerprint": "chrome"}}
  }, {
    "protocol": "hysteria",
    "settings": {"version": 2, "address": "de5.example.net", "port": 8443},
    "streamSettings": {"network": "hysteria", "hysteriaSettings": {"version": 2, "auth": "hunter2-password"}}
  }]
}`

func decode(t *testing.T) any {
	t.Helper()
	var value any
	if err := json.Unmarshal([]byte(config), &value); err != nil {
		t.Fatal(err)
	}
	return value
}

func TestConfigMasksCredentialsOnly(t *testing.T) {
	r := New()
	masked, _ := json.Marshal(r.Config(decode(t)))
	text := string(masked)
	for _, secret := range []string{
		"8cda48b30811", "7xhH4b_VkliBxGulljcyPOH", "6ba85179e30d4fc2", "hunter2-password", "u-0123456789abcdef",
	} {
		if strings.Contains(strings.ToLower(text), strings.ToLower(secret)) {
			t.Errorf("%s survived: %s", secret, text)
		}
	}
	// What a report needs to say which server and how it is reached stays.
	for _, kept := range []string{"de1.example.net", "www.example.com", "xtls-rprx-vision", `"encryption":"none"`, "chrome", "8443"} {
		if !strings.Contains(text, kept) {
			t.Errorf("%s was masked: %s", kept, text)
		}
	}
}

func TestStringUsesRegisteredSecrets(t *testing.T) {
	r := New()
	r.AddConfig(decode(t))
	line := "2026/10/16 [Info] transport/internet/hysteria: auth hunter2-password rejected, shortId 6ba85179e30d4fc2 " +
		"user b831381d-6324-4d53-ad4f-8cda48b30811"
	out := r.String(line)
	if strings.Contains(out, "hunter2") || strings.Contains(out, "6ba85179") || strings.Contains(out, "8cda48b30811") {
		t.Fatalf("leaked: %s", out)
	}
	// The same secret reads the same within a report, whatever its case.
	upper := r.String("B831381D-6324-4D53-AD4F-8CDA48B30811")
	lower := r.String("b831381d-6324-4d53-ad4f-8cda48b30811")
	if upper != lower || !strings.HasPrefix(upper, "[скрыто:") {
		t.Errorf("markers differ: %s vs %s", upper, lower)
	}
}

func TestUnregisteredUUIDsAreMasked(t *testing.T) {
	out := New().String("invalid request user id 0d6a5b2e-1111-4c4c-9c9c-123456789abc")
	if strings.Contains(out, "123456789abc") {
		t.Fatal(out)
	}
}

func TestMarkersDifferBetweenRuns(t *testing.T) {
	if New().String("6ba85179-e30d-4fc2-9b2a-0123456789ab") == New().String("6ba85179-e30d-4fc2-9b2a-0123456789ab") {
		t.Fatal("a marker that is stable across reports identifies the secret")
	}
}

func TestShortValuesAreLeftAlone(t *testing.T) {
	r := New()
	r.Add("ab")
	r.Add("none")
	if out := r.String("about none"); out != "about none" {
		t.Fatal(out)
	}
}

func TestAddURL(t *testing.T) {
	r := New()
	r.AddURL("https://sub.kairavpn.pro/api/sub/Xk3pQ9vT2mWz?token=abcdef123456")
	out := r.String("fetching https://sub.kairavpn.pro/api/sub/Xk3pQ9vT2mWz?token=abcdef123456 then Xk3pQ9vT2mWz alone, token abcdef123456")
	if strings.Contains(out, "Xk3pQ9vT2mWz") || strings.Contains(out, "abcdef123456") {
		t.Fatal(out)
	}
	if !strings.Contains(out, "[ссылка подписки]") {
		t.Fatal(out)
	}
	// Plain path words are not tokens.
	if !strings.Contains(r.String("/api/sub/"), "/api/sub/") {
		t.Fatal("path words masked")
	}
}

func TestLocalAddressIsMasked(t *testing.T) {
	out := New().String("read tcp [2001:db8::1234]:51234->[2001:db8::1]:443: connection reset; " +
		"write udp 192.168.1.5:40000->203.0.113.5:8443: refused")
	if strings.Contains(out, "2001:db8::1234") || strings.Contains(out, "192.168.1.5") {
		t.Fatal(out)
	}
	if !strings.Contains(out, "203.0.113.5:8443") || !strings.Contains(out, "[2001:db8::1]:443") {
		t.Fatal("server address masked: " + out)
	}
}
