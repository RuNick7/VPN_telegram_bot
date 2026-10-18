package check

import (
	"bytes"
	"context"
	"crypto/ecdh"
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/sha256"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"encoding/pem"
	"fmt"
	"io"
	"log"
	"math/big"
	"net"
	"net/http"
	"net/http/httptest"
	"os"
	"strings"
	"testing"
	"time"

	"github.com/xtls/reality"
	xlog "github.com/xtls/xray-core/common/log"
	"github.com/xtls/xray-core/core"
	"github.com/xtls/xray-core/infra/conf/serial"

	"github.com/RuNick7/vpn-check/internal/subscription"
)

// These tests run real Xray on both ends, over loopback: a server the way a
// node runs it, and the check connecting to it from a share link, the way
// the app would. Nothing leaves the machine.

func TestMain(m *testing.M) {
	// Tunnels run in this test binary started again as a worker.
	ServeWorker()
	// Server-side config warnings would otherwise go to stdout.
	xlog.RegisterHandler(discard{})
	os.Exit(m.Run())
}

const testUUID = "b831381d-6324-4d53-ad4f-8cda48b30811"

// site stands in for the internet behind the server: the health check, the
// Cloudflare trace and a download.
func site(t *testing.T) *httptest.Server {
	t.Helper()
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/generate_204":
			w.WriteHeader(http.StatusNoContent)
		case "/cdn-cgi/trace":
			fmt.Fprint(w, "fl=1\nip=203.0.113.7\nloc=NL\ncolo=AMS\nwarp=off\n")
		case "/down":
			w.Write(bytes.Repeat([]byte{'x'}, 256<<10))
		default:
			http.NotFound(w, r)
		}
	}))
	t.Cleanup(server.Close)
	return server
}

func testOptions(base string) Options {
	return Options{
		Timeout:    5 * time.Second,
		Pings:      2,
		PingURL:    base + "/generate_204",
		TraceURL:   base + "/cdn-cgi/trace",
		Probes:     []Probe{{Name: "Сайт", URL: base + "/generate_204", Want: http.StatusNoContent}},
		SpeedBytes: 1,
		SpeedURL:   base + "/down?bytes=%d",
		Parallel:   2,
	}
}

func freePort(t *testing.T, network string) int {
	t.Helper()
	if network == "udp" {
		conn, err := net.ListenPacket("udp", "127.0.0.1:0")
		if err != nil {
			t.Fatal(err)
		}
		defer conn.Close()
		return conn.LocalAddr().(*net.UDPAddr).Port
	}
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	defer listener.Close()
	return listener.Addr().(*net.TCPAddr).Port
}

// node runs an Xray server with one inbound and direct egress.
func node(t *testing.T, inbound map[string]any) {
	t.Helper()
	data, _ := json.Marshal(map[string]any{
		"log":      map[string]any{"loglevel": "none", "access": "none"},
		"inbounds": []any{inbound},
		// Freedom refuses private addresses unless told otherwise, and the
		// stand-in internet here is on loopback.
		"outbounds": []any{map[string]any{"protocol": "freedom", "settings": map[string]any{
			"finalRules": []any{map[string]any{"action": "allow"}},
		}}},
	})
	config, err := serial.LoadJSONConfig(bytes.NewReader(data))
	if err != nil {
		t.Fatalf("server config: %v", err)
	}
	xrayMu.Lock()
	defer xrayMu.Unlock()
	instance, err := core.New(config)
	if err != nil {
		t.Fatalf("server: %v", err)
	}
	if err := instance.Start(); err != nil {
		t.Fatalf("server start: %v", err)
	}
	t.Cleanup(func() { instance.Close() })
}

func targetFromLink(t *testing.T, link string) *subscription.Target {
	t.Helper()
	outbound, name, err := subscription.LinkToOutbound(link)
	if err != nil {
		t.Fatalf("link: %v", err)
	}
	targets := subscription.Targets([]subscription.Profile{{Name: name, Outbounds: []map[string]any{outbound}}})
	if len(targets) != 1 {
		t.Fatalf("want one target, got %d", len(targets))
	}
	return targets[0]
}

func runOne(t *testing.T, opts Options, target *subscription.Target) *Result {
	t.Helper()
	ctx, cancel := context.WithTimeout(context.Background(), time.Minute)
	defer cancel()
	results := NewRunner(opts).Run(ctx, []*subscription.Target{target}, nil)
	result := results[0]
	if testing.Verbose() {
		for _, step := range result.Steps {
			t.Logf("%-20s %-10s %s", step.Name, step.Status, step.Detail)
		}
		t.Logf("verdict %s, cause %q, hints %q", result.Verdict, result.Cause, result.Hints)
		if result.Verdict != Works {
			t.Logf("log:\n%s", strings.Join(result.Log, "\n"))
		}
	}
	return result
}

func requireWorks(t *testing.T, result *Result) {
	t.Helper()
	if result.Verdict != Works {
		t.Fatalf("verdict %s, want %s; cause %q", result.Verdict, Works, result.Cause)
	}
	if len(result.Pings) != 2 {
		t.Errorf("pings %v, want 2", result.Pings)
	}
	if result.Exit["loc"] != "NL" || result.Exit["colo"] != "AMS" {
		t.Errorf("exit %v", result.Exit)
	}
	if result.Mbps <= 0 {
		t.Errorf("speed not measured")
	}
	if len(result.Log) == 0 {
		t.Errorf("no Xray log captured")
	}
	if len(result.Hints) != 0 {
		t.Errorf("hints for a working server: %q", result.Hints)
	}
}

func TestVLESSRaw(t *testing.T) {
	web := site(t)
	port := freePort(t, "tcp")
	node(t, map[string]any{
		"listen": "127.0.0.1", "port": port, "protocol": "vless",
		"settings": map[string]any{"clients": []any{map[string]any{"id": testUUID}}, "decryption": "none"},
	})
	target := targetFromLink(t, fmt.Sprintf("vless://%s@127.0.0.1:%d?type=tcp&security=none#raw", testUUID, port))
	result := runOne(t, testOptions(web.URL), target)
	requireWorks(t, result)
	if step := result.step(StepTCP); step == nil || step.Status != OK {
		t.Errorf("TCP step %+v", step)
	}
}

type realityKeys struct{ private, public string }

func newRealityKeys(t *testing.T) realityKeys {
	t.Helper()
	key, err := ecdh.X25519().GenerateKey(rand.Reader)
	if err != nil {
		t.Fatal(err)
	}
	encode := base64.RawURLEncoding.EncodeToString
	return realityKeys{private: encode(key.Bytes()), public: encode(key.PublicKey().Bytes())}
}

// realityNode runs a REALITY inbound whose target is a local TLS site
// answering for example.com, and returns its port.
func realityNode(t *testing.T, keys realityKeys, transport map[string]any) int {
	t.Helper()
	mask := httptest.NewUnstartedServer(http.HandlerFunc(func(w http.ResponseWriter, _ *http.Request) {
		fmt.Fprint(w, "mask")
	}))
	// The server probes its target with handshakes the target rejects.
	mask.Config.ErrorLog = log.New(io.Discard, "", 0)
	mask.StartTLS()
	t.Cleanup(mask.Close)
	dest := strings.TrimPrefix(mask.URL, "https://")
	port := freePort(t, "tcp")
	stream := map[string]any{
		"network":  "raw",
		"security": "reality",
		"realitySettings": map[string]any{
			"target":      dest,
			"serverNames": []string{"example.com"},
			"privateKey":  keys.private,
			"shortIds":    []string{"0123abcd"},
		},
	}
	flow := "xtls-rprx-vision"
	for key, value := range transport {
		stream[key] = value
		flow = ""
	}
	node(t, map[string]any{
		"listen": "127.0.0.1", "port": port, "protocol": "vless",
		"settings": map[string]any{
			"clients":    []any{map[string]any{"id": testUUID, "flow": flow}},
			"decryption": "none",
		},
		"streamSettings": stream,
	})
	waitForRealityProbe(t, dest)
	return port
}

// waitForRealityProbe waits for the REALITY server to finish probing its
// target. Until it has, an authenticated client's handshake stalls for five
// seconds -- unnoticeable on a node that has been up for a while, a timeout
// for a server started a moment ago.
func waitForRealityProbe(t *testing.T, dest string) {
	t.Helper()
	deadline := time.Now().Add(10 * time.Second)
	for time.Now().Before(deadline) {
		seen, pending := 0, false
		reality.GlobalPostHandshakeRecordsLens.Range(func(key, value any) bool {
			if strings.HasPrefix(key.(string), dest+" ") {
				seen++
				if _, done := value.([]int); !done {
					pending = true
				}
			}
			return true
		})
		if seen > 0 && !pending {
			return
		}
		time.Sleep(20 * time.Millisecond)
	}
	t.Fatal("REALITY server never finished probing its target")
}

// The three shapes REALITY takes in the subscription: raw with Vision on
// its own port, gRPC behind nginx on 443, XHTTP.
func TestVLESSReality(t *testing.T) {
	cases := []struct {
		name, query, kind string
		transport         map[string]any
	}{
		{"raw", "type=tcp&flow=xtls-rprx-vision", "vless · raw · reality · vision", nil},
		{"grpc", "type=grpc&serviceName=svc", "vless · grpc · reality",
			map[string]any{"network": "grpc", "grpcSettings": map[string]any{"serviceName": "svc"}}},
		{"xhttp", "type=xhttp&path=%2Fx&mode=auto", "vless · xhttp · reality",
			map[string]any{"network": "xhttp", "xhttpSettings": map[string]any{"path": "/x"}}},
	}
	for _, tc := range cases {
		t.Run(tc.name, func(t *testing.T) {
			web := site(t)
			keys := newRealityKeys(t)
			port := realityNode(t, keys, tc.transport)
			target := targetFromLink(t, fmt.Sprintf(
				"vless://%s@127.0.0.1:%d?%s&security=reality&sni=example.com&fp=chrome&pbk=%s&sid=0123abcd#reality",
				testUUID, port, tc.query, keys.public))
			if got := target.Kind(); got != tc.kind {
				t.Errorf("kind %q, want %q", got, tc.kind)
			}
			result := runOne(t, testOptions(web.URL), target)
			requireWorks(t, result)
			// Without the key, the handshake reaches the mask site: what a
			// probe from the outside sees.
			if step := result.step(StepTLS); step == nil || step.Status != OK || !strings.Contains(step.Detail, "example.com") {
				t.Errorf("TLS step %+v", step)
			}
		})
	}
}

func TestVLESSRealityWrongKey(t *testing.T) {
	web := site(t)
	port := realityNode(t, newRealityKeys(t), nil)
	stranger := newRealityKeys(t)
	target := targetFromLink(t, fmt.Sprintf(
		"vless://%s@127.0.0.1:%d?type=tcp&security=reality&sni=example.com&fp=chrome&pbk=%s&sid=0123abcd&flow=xtls-rprx-vision#reality",
		testUUID, port, stranger.public))
	opts := testOptions(web.URL)
	opts.Timeout = 8 * time.Second
	result := runOne(t, opts, target)
	if result.Verdict != Broken {
		t.Fatalf("verdict %s, want %s", result.Verdict, Broken)
	}
	if result.Cause == "" {
		t.Errorf("no cause")
	}
	// The server handed the stranger to the mask site; its port and TLS
	// looked fine from outside, so only the tunnel stage failed.
	if step := result.step(StepTCP); step == nil || step.Status != OK {
		t.Errorf("TCP step %+v", step)
	}
	if len(result.Hints) == 0 || !strings.Contains(result.Hints[0], "Сервер не узнал клиента") {
		t.Errorf("hints %q", result.Hints)
	}
}

func TestHysteria2(t *testing.T) {
	web := site(t)
	certPEM, keyPEM, pin := selfSigned(t, "hy.test")
	port := freePort(t, "udp")
	node(t, map[string]any{
		"listen": "127.0.0.1", "port": port, "protocol": "hysteria",
		"settings": map[string]any{"version": 2, "clients": []any{map[string]any{"auth": "secret-auth"}}},
		"streamSettings": map[string]any{
			"network":          "hysteria",
			"hysteriaSettings": map[string]any{"version": 2},
			"security":         "tls",
			"tlsSettings": map[string]any{
				"alpn": []string{"h3"},
				"certificates": []any{map[string]any{
					"certificate": strings.Split(strings.TrimSpace(certPEM), "\n"),
					"key":         strings.Split(strings.TrimSpace(keyPEM), "\n"),
				}},
			},
		},
	})
	target := targetFromLink(t, fmt.Sprintf("hysteria2://secret-auth@127.0.0.1:%d/?sni=hy.test&pinSHA256=%s#hy2", port, pin))
	if !target.UDP {
		t.Fatalf("hysteria2 not marked UDP")
	}
	result := runOne(t, testOptions(web.URL), target)
	requireWorks(t, result)
	if step := result.step(StepTCP); step == nil || step.Status != Skip {
		t.Errorf("TCP step %+v, want skipped for UDP", step)
	}
}

func TestHysteria2WrongAuth(t *testing.T) {
	web := site(t)
	certPEM, keyPEM, pin := selfSigned(t, "hy.test")
	port := freePort(t, "udp")
	node(t, map[string]any{
		"listen": "127.0.0.1", "port": port, "protocol": "hysteria",
		"settings": map[string]any{"version": 2, "clients": []any{map[string]any{"auth": "secret-auth"}}},
		"streamSettings": map[string]any{
			"network":          "hysteria",
			"hysteriaSettings": map[string]any{"version": 2},
			"security":         "tls",
			"tlsSettings": map[string]any{
				"alpn": []string{"h3"},
				"certificates": []any{map[string]any{
					"certificate": strings.Split(strings.TrimSpace(certPEM), "\n"),
					"key":         strings.Split(strings.TrimSpace(keyPEM), "\n"),
				}},
			},
		},
	})
	target := targetFromLink(t, fmt.Sprintf("hysteria2://wrong@127.0.0.1:%d/?sni=hy.test&pinSHA256=%s#hy2", port, pin))
	opts := testOptions(web.URL)
	opts.Timeout = 2 * time.Second
	result := runOne(t, opts, target)
	if result.Verdict != Broken {
		t.Fatalf("verdict %s, want %s", result.Verdict, Broken)
	}
	if !strings.Contains(result.Cause, "auth failed") {
		t.Errorf("cause %q", result.Cause)
	}
	if len(result.Hints) == 0 || !strings.Contains(result.Hints[0], "не принял пароль") {
		t.Errorf("hints %q", result.Hints)
	}
}

func TestClosedPort(t *testing.T) {
	web := site(t)
	port := freePort(t, "tcp")
	target := targetFromLink(t, fmt.Sprintf("vless://%s@127.0.0.1:%d?type=tcp&security=none#closed", testUUID, port))
	result := runOne(t, testOptions(web.URL), target)
	if result.Verdict != Broken {
		t.Fatalf("verdict %s", result.Verdict)
	}
	if result.tcpKind != kindRefused {
		t.Errorf("tcp kind %q", result.tcpKind)
	}
	if len(result.Hints) == 0 || !strings.Contains(result.Hints[0], "никто не принимает соединения") {
		t.Errorf("hints %q", result.Hints)
	}
}

func TestBadConfigIsReported(t *testing.T) {
	web := site(t)
	target := &subscription.Target{
		Protocol: "vless", Address: "127.0.0.1", Port: 1,
		Outbound: map[string]any{"protocol": "vless", "settings": map[string]any{"vnext": "nonsense"}},
	}
	result := runOne(t, testOptions(web.URL), target)
	if result.Verdict != Broken || !strings.Contains(result.Cause, "Xray не принял") {
		t.Fatalf("verdict %s, cause %q", result.Verdict, result.Cause)
	}
}

func selfSigned(t *testing.T, name string) (certPEM, keyPEM, pin string) {
	t.Helper()
	key, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		t.Fatal(err)
	}
	template := &x509.Certificate{
		SerialNumber: big.NewInt(1),
		Subject:      pkix.Name{CommonName: name},
		DNSNames:     []string{name},
		NotBefore:    time.Now().Add(-time.Hour),
		NotAfter:     time.Now().Add(time.Hour),
		KeyUsage:     x509.KeyUsageDigitalSignature,
		ExtKeyUsage:  []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth},
	}
	der, err := x509.CreateCertificate(rand.Reader, template, template, &key.PublicKey, key)
	if err != nil {
		t.Fatal(err)
	}
	keyDER, err := x509.MarshalECPrivateKey(key)
	if err != nil {
		t.Fatal(err)
	}
	sum := sha256.Sum256(der)
	return string(pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: der})),
		string(pem.EncodeToMemory(&pem.Block{Type: "EC PRIVATE KEY", Bytes: keyDER})),
		hex.EncodeToString(sum[:])
}

// The marker is what finds a run in a node's access log: the node has to
// log it as accepted, next to the user it authenticated.
func TestMarkerReachesTheNodeLog(t *testing.T) {
	web := site(t)
	port := freePort(t, "tcp")
	node(t, map[string]any{
		"listen": "127.0.0.1", "port": port, "protocol": "vless", "tag": "vless-in",
		"settings": map[string]any{"clients": []any{map[string]any{"id": testUUID, "email": "u-test"}}, "decryption": "none"},
	})
	target := targetFromLink(t, fmt.Sprintf("vless://%s@127.0.0.1:%d?type=tcp&security=none#raw", testUUID, port))
	opts := testOptions(web.URL)
	opts.RunID = "0a1b2c3d"
	// The client runs in a worker process; what lands here is the node's.
	nodeLog := &capture{}
	xlog.RegisterHandler(nodeLog)
	defer xlog.RegisterHandler(discard{})
	result := runOne(t, opts, target)
	requireWorks(t, result)
	if result.Marker != "vpncheck-0a1b2c3d-01.invalid" || !result.MarkerSent {
		t.Fatalf("marker %q sent %v", result.Marker, result.MarkerSent)
	}
	if result.TunnelAt.IsZero() || result.TunnelTook <= 0 {
		t.Fatalf("tunnel window %v %v", result.TunnelAt, result.TunnelTook)
	}
	for _, line := range nodeLog.stop() {
		if strings.Contains(line, " accepted tcp:"+result.Marker+":80") && strings.HasSuffix(line, " email: u-test") {
			t.Logf("node line: %s", line)
			return
		}
	}
	t.Fatal("no access line with the marker in the node's log")
}

// A gRPC client goes on redialling a dead server after its Xray instance
// is closed. In one process those retries landed in every later server's
// log, and the first of them was blamed for the later server's failures.
func TestEachServerLogsOnlyItself(t *testing.T) {
	web := site(t)
	dead := freePort(t, "tcp")
	port := freePort(t, "tcp")
	node(t, map[string]any{
		"listen": "127.0.0.1", "port": port, "protocol": "vless",
		"settings": map[string]any{"clients": []any{map[string]any{"id": testUUID}}, "decryption": "none"},
	})
	targets := []*subscription.Target{
		targetFromLink(t, fmt.Sprintf("vless://%s@127.0.0.1:%d?type=grpc&serviceName=x&security=none#dead", testUUID, dead)),
		targetFromLink(t, fmt.Sprintf("vless://%s@127.0.0.1:%d?type=tcp&security=none#raw", testUUID, port)),
	}
	opts := testOptions(web.URL)
	opts.Timeout = 2 * time.Second
	ctx, cancel := context.WithTimeout(context.Background(), time.Minute)
	defer cancel()
	results := NewRunner(opts).Run(ctx, targets, nil)
	if len(results) != 2 || results[0].Verdict != Broken {
		t.Fatalf("dead server: %+v", results[0])
	}
	requireWorks(t, results[1])
	for _, line := range results[1].Log {
		if strings.Contains(line, fmt.Sprintf(":%d", dead)) {
			t.Fatalf("second server's log has the first one's line: %s", line)
		}
	}
}
