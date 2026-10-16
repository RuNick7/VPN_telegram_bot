package subscription

import (
	"encoding/base64"
	"strings"
	"testing"
)

// A trimmed copy of what Remnawave hands Happ: two profiles, each a balancer
// over the same servers under different tags, one of them dialled through a
// fragmenting freedom outbound.
const happJSON = `[
 {"remarks": "🇩🇪 Германия", "outbounds": [
   {"tag": "proxy", "protocol": "vless",
    "settings": {"vnext": [{"address": "de1.example.net", "port": 443,
      "users": [{"id": "b831381d-6324-4d53-ad4f-8cda48b30811", "encryption": "none"}]}]},
    "streamSettings": {"network": "grpc", "security": "reality",
      "grpcSettings": {"serviceName": "grpc-svc"},
      "realitySettings": {"serverName": "www.example.com", "fingerprint": "chrome", "publicKey": "pk", "shortId": "ab12"}}},
   {"tag": "proxy-2", "protocol": "hysteria",
    "settings": {"version": 2, "address": "de5.example.net", "port": 8443},
    "streamSettings": {"network": "hysteria", "security": "tls", "hysteriaSettings": {"version": 2, "auth": "secret"},
      "tlsSettings": {"serverName": "de5.example.net", "alpn": ["h3"]}}},
   {"tag": "direct", "protocol": "freedom"},
   {"tag": "block", "protocol": "blackhole"}
 ]},
 {"remarks": "Все серверы", "outbounds": [
   {"tag": "proxy-7", "protocol": "vless",
    "settings": {"vnext": [{"address": "de1.example.net", "port": 443,
      "users": [{"id": "b831381d-6324-4d53-ad4f-8cda48b30811", "encryption": "none"}]}]},
    "streamSettings": {"network": "grpc", "security": "reality",
      "grpcSettings": {"serviceName": "grpc-svc"},
      "realitySettings": {"serverName": "www.example.com", "fingerprint": "chrome", "publicKey": "pk", "shortId": "ab12"}}},
   {"tag": "proxy-8", "protocol": "vless",
    "settings": {"vnext": [{"address": "us1.example.net", "port": 10000,
      "users": [{"id": "b831381d-6324-4d53-ad4f-8cda48b30811", "encryption": "none", "flow": "xtls-rprx-vision"}]}]},
    "streamSettings": {"network": "tcp", "security": "reality",
      "realitySettings": {"serverName": "www.example.org", "fingerprint": "firefox", "publicKey": "pk2", "shortId": "cd34"},
      "sockopt": {"dialerProxy": "fragment"}}},
   {"tag": "fragment", "protocol": "freedom", "settings": {"fragment": {"packets": "tlshello", "length": "100-200", "interval": "10-20"}}}
 ]}
]`

func TestParseHappJSON(t *testing.T) {
	profiles, err := Parse([]byte("\xef\xbb\xbf" + happJSON))
	if err != nil {
		t.Fatal(err)
	}
	if len(profiles) != 2 || profiles[0].Name != "🇩🇪 Германия" {
		t.Fatalf("profiles %+v", profiles)
	}
	targets := Targets(profiles)
	if len(targets) != 3 {
		t.Fatalf("want 3 distinct servers, got %d", len(targets))
	}

	grpc := targets[0]
	if grpc.Endpoint() != "de1.example.net:443" || grpc.Kind() != "vless · grpc · reality" ||
		grpc.SNI != "www.example.com" || grpc.Detail != "serviceName=grpc-svc" {
		t.Errorf("grpc %+v", grpc)
	}
	// The same server under another tag in another profile is one target.
	if strings.Join(grpc.Profiles, "|") != "🇩🇪 Германия|Все серверы" {
		t.Errorf("profiles %q", grpc.Profiles)
	}

	hy := targets[1]
	if !hy.UDP || hy.Kind() != "hysteria2 · tls" || hy.Endpoint() != "de5.example.net:8443" {
		t.Errorf("hysteria %+v", hy)
	}

	raw := targets[2]
	if raw.Kind() != "vless · raw · reality · vision" || raw.Fingerprint != "firefox" {
		t.Errorf("raw %+v", raw)
	}
	if len(raw.Chain) != 1 || str(raw.Chain[0], "tag") != "fragment" {
		t.Errorf("chain %v", raw.Chain)
	}
}

func TestParseRejectsSingBox(t *testing.T) {
	_, err := Parse([]byte(`{"outbounds": [{"type": "vless", "tag": "proxy", "server": "x"}]}`))
	if err == nil || !strings.Contains(err.Error(), "sing-box") {
		t.Fatalf("err %v", err)
	}
}

func TestParseUnknown(t *testing.T) {
	if _, err := Parse([]byte("<html>not found</html>")); err != ErrUnknownFormat {
		t.Fatalf("err %v", err)
	}
	if _, err := Parse([]byte("  \n")); err == nil {
		t.Fatal("empty body parsed")
	}
}

const links = `vless://b831381d-6324-4d53-ad4f-8cda48b30811@de1.example.net:443?type=grpc&serviceName=grpc-svc&security=reality&sni=www.example.com&fp=chrome&pbk=pk&sid=ab12#DE%20gRPC
vless://b831381d-6324-4d53-ad4f-8cda48b30811@us1.example.net:10000?type=tcp&security=reality&sni=www.example.org&pbk=pk2&sid=cd34&flow=xtls-rprx-vision#US
vless://b831381d-6324-4d53-ad4f-8cda48b30811@nl1.example.net:443?type=xhttp&path=%2Fxh&mode=packet-up&security=tls&sni=nl1.example.net&alpn=h2,http/1.1&insecure=1#NL
hysteria2://secret:pass@de5.example.net:8443/?sni=de5.example.net&obfs=salamander&obfs-password=salt&pinSHA256=AB:CD#DE%20Hy2
trojan://trojan-pass@fr1.example.net:443?type=ws&path=%2Fws&host=fr1.example.net&sni=fr1.example.net#FR
ss://YWVzLTI1Ni1nY206c3MtcGFzcw@pl1.example.net:8388#PL
unknown://whatever`

func TestParseLinks(t *testing.T) {
	encoded := base64.StdEncoding.EncodeToString([]byte(links))
	for name, body := range map[string]string{"plain": links, "base64": encoded} {
		t.Run(name, func(t *testing.T) {
			profiles, err := Parse([]byte(body))
			if err != nil {
				t.Fatal(err)
			}
			if len(profiles) != 6 {
				t.Fatalf("want 6 profiles (unknown scheme skipped), got %d", len(profiles))
			}
			targets := Targets(profiles)
			want := []struct{ name, endpoint, kind string }{
				{"DE gRPC", "de1.example.net:443", "vless · grpc · reality"},
				{"US", "us1.example.net:10000", "vless · raw · reality · vision"},
				{"NL", "nl1.example.net:443", "vless · xhttp · tls"},
				{"DE Hy2", "de5.example.net:8443", "hysteria2 · tls"},
				{"FR", "fr1.example.net:443", "trojan · ws · tls"},
				{"PL", "pl1.example.net:8388", "shadowsocks · raw"},
			}
			for i, w := range want {
				got := targets[i]
				if got.Name() != w.name || got.Endpoint() != w.endpoint || got.Kind() != w.kind {
					t.Errorf("%d: %s %s %s, want %+v", i, got.Name(), got.Endpoint(), got.Kind(), w)
				}
			}
			if fp := targets[1].Fingerprint; fp != "chrome" {
				t.Errorf("REALITY fingerprint default %q", fp)
			}
			nl := obj(obj(targets[2].Outbound, "streamSettings"), "tlsSettings")
			if _, ok := nl["allowInsecure"]; ok {
				t.Error("allowInsecure is refused by Xray 26 and must not be emitted")
			}
			hy := obj(targets[3].Outbound, "streamSettings")
			if obj(hy, "hysteriaSettings")["auth"] != "secret:pass" || obj(hy, "tlsSettings")["pinnedPeerCertSha256"] != "AB:CD" {
				t.Errorf("hysteria stream %v", hy)
			}
			if hy["finalmask"] == nil {
				t.Error("salamander obfuscation dropped")
			}
			ss := obj(targets[5].Outbound, "settings")
			if ss["method"] != "aes-256-gcm" || ss["password"] != "ss-pass" {
				t.Errorf("ss %v", ss)
			}
		})
	}
}

func TestVMessLink(t *testing.T) {
	body := `{"v":"2","ps":"VM","add":"vm.example.net","port":"443","id":"b831381d-6324-4d53-ad4f-8cda48b30811","net":"ws","path":"/vm","host":"vm.example.net","tls":"tls","sni":"vm.example.net"}`
	outbound, name, err := LinkToOutbound("vmess://" + base64.StdEncoding.EncodeToString([]byte(body)))
	if err != nil {
		t.Fatal(err)
	}
	target := describe(outbound)
	if name != "VM" || target.Endpoint() != "vm.example.net:443" || target.Kind() != "vmess · ws · tls" {
		t.Errorf("%s %s %s", name, target.Endpoint(), target.Kind())
	}
}

func TestLinkErrors(t *testing.T) {
	for _, link := range []string{
		"vless://id@host#no-port",
		"vless://id@:443#no-host",
		"ss://not-base64!@#",
		"vmess://%%%",
	} {
		if _, _, err := LinkToOutbound(link); err == nil {
			t.Errorf("%s parsed", link)
		}
	}
}
