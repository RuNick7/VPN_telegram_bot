package check

import (
	"strings"
	"testing"
	"time"

	"github.com/RuNick7/vpn-check/internal/subscription"
)

// Every kind of link the parser reads has to produce an outbound that this
// Xray accepts: a config error would read as a dead server.
func TestLinkOutboundsLoadInXray(t *testing.T) {
	for _, link := range []string{
		"vless://b831381d-6324-4d53-ad4f-8cda48b30811@de1.example.net:443?type=grpc&serviceName=s&security=reality&sni=www.example.com&fp=chrome&pbk=7xhH4b_VkliBxGulljcyPOH-bYUA2dl-XAdZAsfhk04&sid=ab12#a",
		"vless://b831381d-6324-4d53-ad4f-8cda48b30811@us1.example.net:10000?type=tcp&security=reality&sni=www.example.org&pbk=7xhH4b_VkliBxGulljcyPOH-bYUA2dl-XAdZAsfhk04&sid=cd34&flow=xtls-rprx-vision#b",
		"vless://b831381d-6324-4d53-ad4f-8cda48b30811@nl1.example.net:443?type=xhttp&path=%2Fxh&mode=packet-up&security=tls&sni=nl1.example.net&alpn=h2&insecure=1#c",
		"hysteria2://secret@de5.example.net:8443/?sni=de5.example.net&obfs=salamander&obfs-password=salt#d",
		"trojan://trojan-pass@fr1.example.net:443?type=ws&path=%2Fws&host=fr1.example.net&sni=fr1.example.net#e",
		"ss://YWVzLTI1Ni1nY206c3MtcGFzcw@pl1.example.net:8388#f",
	} {
		outbound, _, err := subscription.LinkToOutbound(link)
		if err != nil {
			t.Fatalf("%s: %v", link, err)
		}
		xrayMu.Lock()
		instance, err := startXray(&subscription.Target{Outbound: outbound}, &capture{})
		xrayMu.Unlock()
		if err != nil {
			t.Errorf("%s: %v", link, err)
			continue
		}
		instance.Close()
	}
}

func TestXrayCause(t *testing.T) {
	cases := map[string][]string{
		"x509: certificate signed by unknown authority": {
			"2026/10/16 19:23:57.485094 [Debug] transport/internet: dialing to tcp:127.0.0.1:35647",
			"2026/10/16 19:23:59.504668 [Info] app/proxyman/outbound: app/proxyman/outbound: failed to process outbound traffic > " +
				"proxy/vless/outbound: failed to find an available destination > common/retry: [x509: certificate signed by unknown authority] > " +
				"common/retry: all retry attempts failed",
			"2026/10/16 19:23:59.504800 [Debug] app/log: Logger closing",
		},
		"tls: invalid server key share": {
			`2026/10/16 10:00:00.000000 [Info] [123] proxy/vless/outbound: failed to find an available destination > ` +
				`common/retry: [rpc error: code = Unavailable desc = "connection error: desc = \"transport: authentication handshake failed: tls: invalid server key share\""] > common/retry: all retry attempts failed`,
		},
		"": {
			"2026/10/17 23:13:00.070670 [Warning] common/errors: The feature gRPC transport (with unnecessary costs, etc.) is deprecated, " +
				"not recommended for using and might be removed. Please migrate to XHTTP stream-up H2 as soon as possible.",
			"2026/10/16 10:00:00.000000 [Warning] core: Xray 26.7.28 started",
			"2026/10/16 10:00:00.000000 [Info] app/dispatcher: default route for tcp:1.1.1.1:80",
		},
	}
	for want, lines := range cases {
		got := xrayCause(lines)
		if !strings.Contains(got, want) || (want == "" && got != "") {
			t.Errorf("xrayCause = %q, want %q", got, want)
		}
	}
}

func realityTarget(sni, fp string) *subscription.Target {
	return &subscription.Target{Protocol: "vless", Address: "de1.example.net", Port: 443, Security: "reality", SNI: sni, Fingerprint: fp}
}

func TestHints(t *testing.T) {
	cases := []struct {
		name   string
		result *Result
		want   string
	}{
		{"target unreachable from the node", &Result{
			Target: realityTarget("www.example.com", "chrome"), tlsKind: kindTimeout,
			Steps: []Step{{Name: StepTCP, Status: OK}, {Name: StepTLS, Status: Fail}, {Name: StepPing, Status: Fail}},
		}, "нода не достаёт до сайта-маски"},
		{"P-256 target with firefox", &Result{
			Target: realityTarget("www.example.com", "firefox"), curve: "P256", Cause: "tls: invalid server key share",
			Steps: []Step{{Name: StepTCP, Status: OK}, {Name: StepTLS, Status: OK}, {Name: StepPing, Status: Fail}},
		}, "fingerprint"},
		{"wrong SNI", &Result{
			Target: &subscription.Target{Protocol: "hysteria", Address: "de5.example.net", Port: 8443, Security: "tls", SNI: "de5.example.net", UDP: true},
			Cause:  "tls: failed to verify certificate: x509: certificate is valid for de1.example.net, not de5.example.net",
			Steps:  []Step{{Name: StepTCP, Status: Skip}, {Name: StepPing, Status: Fail}},
		}, "не тот SNI"},
		{"nginx forwards to nothing", &Result{
			Target: realityTarget("www.example.com", "chrome"), Cause: "connection refused",
			Steps: []Step{{Name: StepTCP, Status: OK}, {Name: StepTLS, Status: OK}, {Name: StepPing, Status: Fail}},
		}, "уже внутри протокола"},
		{"expired certificate", &Result{
			Target: &subscription.Target{Protocol: "hysteria", Address: "fl2.example.net", Port: 9997, Security: "tls", UDP: true},
			Cause: "CRYPTO_ERROR 0x12a (local): tls: failed to verify certificate: x509: certificate has expired or is not yet valid: " +
				"“fl2.example.net” certificate is expired",
			Steps: []Step{{Name: StepTCP, Status: Skip}, {Name: StepPing, Status: Fail}},
		}, "просрочен"},
		{"UDP cut", &Result{
			Target: &subscription.Target{Protocol: "hysteria", Address: "de5.example.net", Port: 8443, Security: "tls", UDP: true},
			Cause:  "timeout: no recent network activity",
			Steps:  []Step{{Name: StepTCP, Status: Skip}, {Name: StepPing, Status: Fail}},
		}, "UDP"},
		{"DNS lies", &Result{
			Target: realityTarget("www.example.com", "chrome"),
			Steps:  []Step{{Name: StepDNS, Status: Warn}, {Name: StepTCP, Status: OK}, {Name: StepPing, Status: OK}},
			Pings:  nil,
		}, "подменять"},
		{"Telegram blocked behind a working tunnel", &Result{
			Target: realityTarget("www.example.com", "chrome"),
			Steps:  []Step{{Name: StepPing, Status: OK}, {Name: "Telegram", Status: Fail}},
		}, "Telegram"},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			judge(tc.result)
			if !strings.Contains(strings.Join(tc.result.Hints, "\n"), tc.want) {
				t.Errorf("hints %q, want one mentioning %q", tc.result.Hints, tc.want)
			}
		})
	}
}

func TestJudge(t *testing.T) {
	works := &Result{Target: realityTarget("a", "chrome"), Steps: []Step{{Name: StepDNS, Status: Warn}, {Name: StepPing, Status: OK}, {Name: StepExit, Status: OK}}}
	judge(works)
	if works.Verdict != Works {
		t.Errorf("a warning before the tunnel made it %s", works.Verdict)
	}
	partial := &Result{Target: realityTarget("a", "chrome"), Steps: []Step{{Name: StepPing, Status: OK}, {Name: "Google", Status: Warn}}}
	judge(partial)
	if partial.Verdict != Partial {
		t.Errorf("verdict %s", partial.Verdict)
	}
	broken := &Result{Target: realityTarget("a", "chrome"), Steps: []Step{{Name: StepTCP, Status: OK}}}
	judge(broken)
	if broken.Verdict != Broken {
		t.Errorf("no tunnel step, verdict %s", broken.Verdict)
	}
}

func TestClockFrom(t *testing.T) {
	sent := time.Unix(1_790_000_000, 0)
	// Cloudflare's clock is 3 s ahead; the reply took 400 ms, so the
	// moment it describes is 200 ms after sending.
	clock := clockFrom("1790000003.200", sent, 400*time.Millisecond)
	if !clock.Known || clock.Offset != 3*time.Second {
		t.Fatalf("%+v", clock)
	}
	for _, ts := range []string{"", "soon", "-5"} {
		if clockFrom(ts, sent, 0).Known {
			t.Errorf("%q read as a time", ts)
		}
	}
	if Marker("0a1b2c3d", 7) != "vpncheck-0a1b2c3d-07.invalid" {
		t.Error(Marker("0a1b2c3d", 7))
	}
}
