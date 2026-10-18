package check

import (
	"bytes"
	"context"
	"encoding/json"
	"fmt"
	"io"
	"net"
	"net/http"
	"regexp"
	"strings"
	"sync"
	"time"

	xlog "github.com/xtls/xray-core/common/log"
	xnet "github.com/xtls/xray-core/common/net"
	"github.com/xtls/xray-core/core"
	"github.com/xtls/xray-core/infra/conf/serial"

	// Every protocol and transport Xray's own binary has, so any outbound a
	// subscription can contain loads here the way it loads in the app.
	_ "github.com/xtls/xray-core/main/distro/all"

	"github.com/RuNick7/vpn-check/internal/subscription"
)

// Step names for what goes through the tunnel.
const (
	StepPing  = "Пинг через сервер"
	StepExit  = "Выход в интернет"
	StepSpeed = "Скорость"
)

// XrayVersion is the core compiled in, which is what decides whether a
// check behaves like the client app: Happ 5.5 ships 26.7.28.
func XrayVersion() string { return core.Version() }

// Xray logs through one process-wide handler, so only one instance may run
// at a time if each server's log is to hold only that server's lines.
var xrayMu sync.Mutex

// maxLogLines bounds one server's log. A healthy check writes a few hundred
// lines at debug level; this is for the one that loops on retries.
const maxLogLines = 5000

type capture struct {
	mu     sync.Mutex
	lines  []string
	closed bool
}

func (c *capture) Handle(msg xlog.Message) {
	line := time.Now().Format("2006/01/02 15:04:05.000000") + " " + msg.String()
	c.mu.Lock()
	defer c.mu.Unlock()
	switch {
	case c.closed:
	case len(c.lines) < maxLogLines:
		c.lines = append(c.lines, line)
	case len(c.lines) == maxLogLines:
		c.lines = append(c.lines, "... дальше лог обрезан")
	}
}

// mark is where the log stands now, for since.
func (c *capture) mark() int {
	c.mu.Lock()
	defer c.mu.Unlock()
	return len(c.lines)
}

// since is what was logged after mark: the lines that can explain one
// request, and not an earlier request's failure.
func (c *capture) since(mark int) []string {
	c.mu.Lock()
	defer c.mu.Unlock()
	return append([]string(nil), c.lines[min(mark, len(c.lines)):]...)
}

func (c *capture) stop() []string {
	c.mu.Lock()
	defer c.mu.Unlock()
	c.closed = true
	return c.lines
}

type discard struct{}

func (discard) Handle(xlog.Message) {}

// tunnelHere connects through the server with Xray and makes the requests a
// person would: the health check the app's balancer pings, then real sites.
// It runs in a worker process (see tunnel).
func (r *Runner) tunnelHere(ctx context.Context, result *Result) {
	xrayMu.Lock()
	defer xrayMu.Unlock()

	logs := &capture{}
	xlog.RegisterHandler(logs)
	defer func() {
		// Late lines from connections still closing belong to nobody's report.
		xlog.RegisterHandler(discard{})
		result.Log = logs.stop()
	}()

	instance, err := startXray(result.Target, logs)
	if err != nil {
		result.Cause = "Xray не принял настройки сервера: " + err.Error()
		result.add(Step{Name: StepPing, Status: Fail, Detail: result.Cause})
		return
	}
	defer instance.Close()
	client := httpThrough(instance, r.opts.Timeout)
	// Last, so whatever it makes Xray log comes after every line the checks
	// above are judged by -- and still sent when they failed, as a node whose
	// own outbound is broken logs the request all the same.
	defer r.mark(ctx, client, result)

	if !r.pings(ctx, client, result, logs) {
		return
	}
	r.exit(ctx, client, result)
	for _, probe := range r.opts.Probes {
		r.probe(ctx, client, result, probe, logs)
	}
	if r.opts.SpeedBytes > 0 {
		r.speed(ctx, client, result)
	}
}

// mark asks for the run's marker host through the server. The answer does
// not matter and cannot be good: what counts is the line the node's access
// log writes when it accepts the request.
func (r *Runner) mark(ctx context.Context, client *http.Client, result *Result) {
	if result.Marker == "" || ctx.Err() != nil {
		return
	}
	mctx, cancel := context.WithTimeout(ctx, min(3*time.Second, r.opts.Timeout))
	defer cancel()
	_, _, _, _ = get(mctx, client, "http://"+result.Marker+"/")
	result.MarkerSent = true
}

// pings makes the health-check request over a fresh connection each time.
// The first failure ends the check: nothing after it would get further, and
// waiting out the same timeout again only makes the whole run slower.
func (r *Runner) pings(ctx context.Context, client *http.Client, result *Result, logs *capture) bool {
	step := Step{Name: StepPing, Status: OK}
	var timings []string
	for i := 0; i < r.opts.Pings; i++ {
		from := logs.mark()
		status, _, took, err := get(ctx, client, r.opts.PingURL)
		step.Took += took
		if err != nil {
			result.Cause = tunnelCause(err, logs.since(from))
			if len(result.Pings) == 0 {
				step.Status = Fail
				step.Detail = fmt.Sprintf("%s — нет ответа за %s: %s", r.opts.PingURL, ms(took), result.Cause)
				result.add(step)
				return false
			}
			step.Status = Warn
			timings = append(timings, "ошибка: "+result.Cause)
			break
		}
		if status != http.StatusNoContent {
			step.Status = Warn
			timings = append(timings, fmt.Sprintf("%s (HTTP %d)", ms(took), status))
		} else {
			timings = append(timings, ms(took))
		}
		result.Pings = append(result.Pings, took)
	}
	step.Detail = fmt.Sprintf("%s — %s", r.opts.PingURL, strings.Join(timings, ", "))
	result.add(step)
	return true
}

// exit asks Cloudflare who it sees: the node's address and country, and
// whether the node sends this traffic through WARP.
func (r *Runner) exit(ctx context.Context, client *http.Client, result *Result) {
	if r.opts.TraceURL == "" {
		return
	}
	status, body, took, err := get(ctx, client, r.opts.TraceURL)
	step := Step{Name: StepExit, Took: took}
	switch {
	case err != nil:
		step.Status, step.Detail = Fail, shortHTTPError(err)
	case status != http.StatusOK:
		step.Status, step.Detail = Warn, fmt.Sprintf("HTTP %d", status)
	default:
		result.Exit = parseTrace(body)
		step.Status = OK
		step.Detail = fmt.Sprintf("IP %s, страна %s, Cloudflare %s, WARP %s — за %s",
			orDash(result.Exit["ip"]), orDash(result.Exit["loc"]), orDash(result.Exit["colo"]),
			orDash(result.Exit["warp"]), ms(took))
	}
	result.add(step)
}

func (r *Runner) probe(ctx context.Context, client *http.Client, result *Result, probe Probe, logs *capture) {
	from := logs.mark()
	status, _, took, err := get(ctx, client, probe.URL)
	step := Step{Name: probe.Name, Took: took}
	switch {
	case err != nil:
		step.Status = Fail
		step.Detail = fmt.Sprintf("%s — %s", probe.URL, tunnelCause(err, logs.since(from)))
	case probe.Want != 0 && status != probe.Want:
		step.Status = Warn
		step.Detail = fmt.Sprintf("%s — HTTP %d вместо %d за %s", probe.URL, status, probe.Want, ms(took))
	default:
		step.Status = OK
		step.Detail = fmt.Sprintf("%s — HTTP %d за %s", probe.URL, status, ms(took))
	}
	result.add(step)
}

func (r *Runner) speed(ctx context.Context, client *http.Client, result *Result) {
	url := fmt.Sprintf(r.opts.SpeedURL, r.opts.SpeedBytes)
	sctx, cancel := context.WithTimeout(ctx, 6*r.opts.Timeout)
	defer cancel()
	step := Step{Name: StepSpeed}
	req, _ := http.NewRequestWithContext(sctx, http.MethodGet, url, nil)
	req.Header.Set("User-Agent", userAgent)
	started := time.Now()
	resp, err := client.Do(req)
	var read int64
	if err == nil {
		read, err = io.Copy(io.Discard, resp.Body)
		resp.Body.Close()
	}
	step.Took = time.Since(started)
	if read > 0 {
		result.Mbps = float64(read) * 8 / step.Took.Seconds() / 1e6
	}
	switch {
	case read == 0 && err != nil:
		step.Status, step.Detail = Fail, shortHTTPError(err)
	case err != nil:
		step.Status = Warn
		step.Detail = fmt.Sprintf("%.1f Мбит/с, скачано %.1f МБ за %.1f с, затем обрыв: %s",
			result.Mbps, float64(read)/(1<<20), step.Took.Seconds(), shortHTTPError(err))
	default:
		step.Status = OK
		step.Detail = fmt.Sprintf("%.1f Мбит/с (%.1f МБ за %.1f с)", result.Mbps, float64(read)/(1<<20), step.Took.Seconds())
	}
	result.add(step)
}

func startXray(target *subscription.Target, logs *capture) (*core.Instance, error) {
	outbounds := []any{sanitize(target.Outbound)}
	for _, hop := range target.Chain {
		outbounds = append(outbounds, sanitize(hop))
	}
	data, err := json.Marshal(map[string]any{
		// Xray's own writers stay silent: every line goes to logs instead.
		"log":       map[string]any{"loglevel": "none", "access": "none"},
		"outbounds": outbounds,
	})
	if err != nil {
		return nil, err
	}
	config, err := serial.LoadJSONConfig(bytes.NewReader(data))
	if err != nil {
		return nil, err
	}
	instance, err := core.New(config)
	if err != nil {
		return nil, err
	}
	// core.New installs Xray's own log handler; take the log back from it.
	xlog.RegisterHandler(logs)
	if err := instance.Start(); err != nil {
		instance.Close()
		return nil, err
	}
	return instance, nil
}

// sanitize copies an outbound and switches off what would leak or print:
// REALITY's `show` writes key material to stdout, and `masterKeyLog` writes
// TLS secrets to a file.
func sanitize(outbound map[string]any) map[string]any {
	var copied map[string]any
	data, _ := json.Marshal(outbound)
	_ = json.Unmarshal(data, &copied)
	stream, _ := copied["streamSettings"].(map[string]any)
	if reality, ok := stream["realitySettings"].(map[string]any); ok {
		reality["show"] = false
		delete(reality, "masterKeyLog")
	}
	if tls, ok := stream["tlsSettings"].(map[string]any); ok {
		delete(tls, "masterKeyLog")
	}
	return copied
}

func httpThrough(instance *core.Instance, timeout time.Duration) *http.Client {
	transport := &http.Transport{
		Proxy: nil,
		DialContext: func(ctx context.Context, network, address string) (net.Conn, error) {
			dest, err := xnet.ParseDestination(network + ":" + address)
			if err != nil {
				return nil, err
			}
			return core.Dial(ctx, instance, dest)
		},
		// A fresh tunnel connection per request, as the balancer's health
		// check makes it: the handshake is the part that breaks.
		DisableKeepAlives:     true,
		TLSHandshakeTimeout:   timeout,
		ResponseHeaderTimeout: timeout,
	}
	return &http.Client{Transport: transport, Timeout: timeout, CheckRedirect: noRedirect}
}

func noRedirect(*http.Request, []*http.Request) error { return http.ErrUseLastResponse }

const userAgent = "Mozilla/5.0 (compatible; vpncheck)"

func get(ctx context.Context, client *http.Client, url string) (int, []byte, time.Duration, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodGet, url, nil)
	if err != nil {
		return 0, nil, 0, err
	}
	req.Header.Set("User-Agent", userAgent)
	started := time.Now()
	resp, err := client.Do(req)
	if err != nil {
		return 0, nil, time.Since(started), err
	}
	defer resp.Body.Close()
	body, err := io.ReadAll(io.LimitReader(resp.Body, 64<<10))
	return resp.StatusCode, body, time.Since(started), err
}

func parseTrace(body []byte) map[string]string {
	fields := map[string]string{}
	for _, line := range strings.Split(string(body), "\n") {
		key, value, ok := strings.Cut(strings.TrimSpace(line), "=")
		if ok && (key == "ip" || key == "loc" || key == "colo" || key == "warp" || key == "ts") {
			fields[key] = value
		}
	}
	return fields
}

// tunnelCause explains a failed request through the tunnel.
//
// What the HTTP client sees is useless on its own -- "EOF", or a timeout --
// because the connection to the server is made inside Xray. The reason is in
// Xray's log, at the end of the chain of "failed to ... >" it prints.
func tunnelCause(err error, lines []string) string {
	if cause := xrayCause(lines); cause != "" {
		return cause
	}
	return shortHTTPError(err)
}

// linePrefix is what capture puts before a message, plus the severity and
// the session id Xray puts there itself.
var linePrefix = regexp.MustCompile(`^\d{4}/\d\d/\d\d \d\d:\d\d:\d\d\.\d+ \[\w+\] (\[\d+\] )?`)

func xrayCause(lines []string) string {
	for i := len(lines) - 1; i >= 0; i-- {
		line := lines[i]
		if !strings.Contains(line, "failed to") && !strings.Contains(line, "[Error]") && !strings.Contains(line, "[Warning]") {
			continue
		}
		// Xray's start line, and its notices that a feature is deprecated:
		// warnings, but never why a request failed.
		if strings.Contains(line, "core: Xray") || strings.Contains(line, "deprecated") {
			continue
		}
		segments := strings.Split(linePrefix.ReplaceAllString(line, ""), " > ")
		for len(segments) > 1 && strings.Contains(segments[len(segments)-1], "all retry attempts failed") {
			segments = segments[:len(segments)-1]
		}
		cause := strings.TrimPrefix(segments[len(segments)-1], "common/retry: [")
		cause = strings.TrimSuffix(cause, "]")
		if index := strings.LastIndex(cause, `desc = "`); index >= 0 {
			cause = strings.TrimSuffix(cause[index+len(`desc = "`):], `"`)
		}
		return strings.TrimSpace(cause)
	}
	return ""
}

func shortHTTPError(err error) string {
	text := err.Error()
	// net/http wraps everything in `Get "url": ...`; the URL is already said.
	if _, after, ok := strings.Cut(text, `": `); ok {
		text = after
	}
	return text
}

func orDash(value string) string {
	if value == "" {
		return "—"
	}
	return value
}
