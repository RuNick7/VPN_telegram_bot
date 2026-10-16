package check

import (
	"context"
	"fmt"
	"net"
	"net/http"
	"sync"
	"time"

	"github.com/RuNick7/VPN_telegram_bot/vpncheck/internal/subscription"
)

// Probe is a request made through each server once it answers.
type Probe struct {
	Name string
	URL  string
	// The status that counts as success; 0 accepts any answer, for a site
	// whose reachability is the question and whose reply is not.
	Want int
}

type Options struct {
	// Each request through a server, and each of the network stages.
	Timeout time.Duration
	Pings   int
	// The template's burstObservatory destination (vpn-diagnostics/fix-plan.md,
	// step 2): plain HTTP, so it costs one round trip inside the tunnel and
	// never touches WARP on the node.
	PingURL  string
	TraceURL string
	Probes   []Probe
	// Public resolvers to compare the system's answer with. 77.88.8.8 is the
	// one the template resolves kairavpn.pro through.
	Resolvers []string
	// How much to download through each server to measure speed; 0 skips it.
	SpeedBytes int64
	SpeedURL   string
	// How many servers to run the network stages for at once. The tunnel
	// stage always runs one server at a time.
	Parallel int
}

func DefaultOptions() Options {
	return Options{
		Timeout:  10 * time.Second,
		Pings:    3,
		PingURL:  "http://cp.cloudflare.com/generate_204",
		TraceURL: "https://cloudflare.com/cdn-cgi/trace",
		Probes: []Probe{
			{Name: "Google", URL: "https://www.google.com/generate_204", Want: http.StatusNoContent},
			{Name: "Telegram", URL: "https://api.telegram.org/"},
		},
		Resolvers: []string{"77.88.8.8:53", "1.1.1.1:53"},
		SpeedURL:  "https://speed.cloudflare.com/__down?bytes=%d",
		Parallel:  8,
	}
}

type Runner struct{ opts Options }

func NewRunner(opts Options) *Runner { return &Runner{opts: opts} }

// Run checks every target and reports each as it finishes. Cancelled midway,
// it returns the servers it finished, in order.
//
// The network stages for all servers run first and side by side: they are
// independent and mostly waiting. The tunnels then run one after another,
// because Xray's log is process-wide and each server's report has to hold
// that server's lines and no other's.
func (r *Runner) Run(ctx context.Context, targets []*subscription.Target, done func(int, *Result)) []*Result {
	results := make([]*Result, len(targets))
	limit := make(chan struct{}, max(1, r.opts.Parallel))
	var wg sync.WaitGroup
	for i, target := range targets {
		results[i] = &Result{Target: target}
		wg.Add(1)
		go func() {
			defer wg.Done()
			limit <- struct{}{}
			defer func() { <-limit }()
			r.network(ctx, results[i])
		}()
	}
	wg.Wait()

	for i, result := range results {
		if ctx.Err() != nil {
			return results[:i]
		}
		started := time.Now()
		r.tunnel(ctx, result)
		result.Took += time.Since(started)
		if ctx.Err() != nil {
			// Cut short by the user, not by the server.
			return results[:i]
		}
		judge(result)
		if done != nil {
			done(i, result)
		}
	}
	return results
}

func (r *Runner) network(ctx context.Context, result *Result) {
	result.Started = time.Now()
	defer func() { result.Took = time.Since(result.Started) }()
	target := result.Target

	step, ips := probeDNS(ctx, target.Address, r.opts.Resolvers, r.opts.Timeout)
	result.add(step)
	result.ips = ips

	if target.UDP {
		result.add(Step{Name: StepTCP, Status: Skip, Detail: "сервер работает по UDP — ответит ли он, покажет только сам протокол ниже"})
		return
	}
	tcp, kind := probeTCP(ctx, ips, target.Port, r.opts.Timeout)
	result.add(tcp)
	result.tcpKind = kind
	if tcp.Status != OK || (target.Security != "tls" && target.Security != "reality") {
		return
	}
	shake := probeTLS(ctx, ips[0], target.Port, target.SNI, target.Security, r.opts.Timeout)
	result.add(shake.step)
	result.tlsKind, result.curve, result.certNames = shake.kind, shake.curve, shake.names
}

// judge sets the verdict and the hints once every stage has run.
func judge(result *Result) {
	ping := result.step(StepPing)
	switch {
	case ping == nil || ping.Status == Fail:
		result.Verdict = Broken
	default:
		// Only what went through the tunnel decides it. A warning before it
		// -- DNS answers that differ, a target's certificate -- is a hint
		// about the setup, not a connection that failed.
		result.Verdict = Works
		throughTunnel := false
		for _, step := range result.Steps {
			throughTunnel = throughTunnel || step.Name == StepPing
			if throughTunnel && (step.Status == Fail || step.Status == Warn) {
				result.Verdict = Partial
			}
		}
	}
	result.Hints = hints(result)
}

// Baseline checks the computer's own connection, without any server in
// between, so a report can tell "every server fails" from "the internet is
// down" -- and notice a VPN left running, which would carry every check
// through itself.
func Baseline(ctx context.Context, opts Options) []Step {
	client := &http.Client{
		Transport:     &http.Transport{Proxy: nil, DisableKeepAlives: true},
		Timeout:       opts.Timeout,
		CheckRedirect: noRedirect,
	}
	var steps []Step
	status, _, took, err := get(ctx, client, opts.PingURL)
	switch {
	case err != nil:
		steps = append(steps, Step{Name: "Интернет без VPN", Status: Fail, Took: took,
			Detail: fmt.Sprintf("%s — %s", opts.PingURL, shortHTTPError(err))})
	default:
		steps = append(steps, Step{Name: "Интернет без VPN", Status: OK, Took: took,
			Detail: fmt.Sprintf("%s — HTTP %d за %s", opts.PingURL, status, ms(took))})
	}
	if opts.TraceURL != "" {
		status, body, took, err := get(ctx, client, opts.TraceURL)
		if err == nil && status == http.StatusOK {
			trace := parseTrace(body)
			// The address is the customer's own; the country and the
			// Cloudflare city are enough to tell where the check ran from.
			steps = append(steps, Step{Name: "Откуда проверка", Status: OK, Took: took,
				Detail: fmt.Sprintf("страна %s, Cloudflare %s", orDash(trace["loc"]), orDash(trace["colo"]))})
		}
	}
	if name := activeTunnel(); name != "" {
		steps = append(steps, Step{Name: "Другой VPN", Status: Warn, Detail: fmt.Sprintf(
			"похоже, включён VPN (интерфейс %s): проверки пойдут через него, результаты будут неверными", name)})
	}
	return steps
}

// activeTunnel names a network interface that looks like a running VPN
// client's TUN: Happ and Xray put theirs in 198.18.0.0/15, sing-box in
// 172.19.0.0/30 (the "Happ Tunnel" with DNS 172.19.0.2 in report 3).
func activeTunnel() string {
	interfaces, err := net.Interfaces()
	if err != nil {
		return ""
	}
	_, benchmark, _ := net.ParseCIDR("198.18.0.0/15")
	_, singbox, _ := net.ParseCIDR("172.19.0.0/30")
	for _, iface := range interfaces {
		if iface.Flags&net.FlagUp == 0 || iface.Flags&net.FlagLoopback != 0 {
			continue
		}
		addrs, _ := iface.Addrs()
		for _, addr := range addrs {
			ipnet, ok := addr.(*net.IPNet)
			if ok && (benchmark.Contains(ipnet.IP) || singbox.Contains(ipnet.IP)) {
				return iface.Name
			}
		}
	}
	return ""
}
