package check

import (
	"context"
	"fmt"
	"net"
	"net/http"
	"strconv"
	"sync"
	"time"

	"github.com/RuNick7/vpn-check/internal/subscription"
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
	// The subscription template's burstObservatory destination: plain
	// HTTP, so it costs one round trip inside the tunnel and never touches
	// WARP on the node.
	PingURL  string
	TraceURL string
	Probes   []Probe
	// Public resolvers to compare the system's answer with. 77.88.8.8 is the
	// one the template resolves kairavpn.pro through.
	Resolvers []string
	// How much to download through each server to measure speed; 0 skips it.
	SpeedBytes int64
	SpeedURL   string
	// Names this run in the nodes' access logs: each server gets one request
	// to a host made from it (see Marker), which a node's log records next to
	// the user it authenticated. Empty sends no marker.
	RunID string
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

type Runner struct {
	opts     Options
	progress Progress
}

func NewRunner(opts Options) *Runner { return &Runner{opts: opts} }

// Progress is told where a run is, for a window that shows it as it goes.
// Either may be nil. Network is called from several goroutines at once.
type Progress struct {
	// Network: server i's network stages are done. They run for every
	// server side by side before any tunnel does.
	Network func(i int)
	// Tunnel: server i's tunnel is about to start.
	Tunnel func(i int)
}

// Watch sets who is told about the run's progress.
func (r *Runner) Watch(progress Progress) *Runner {
	r.progress = progress
	return r
}

// Run checks every target and reports each as it finishes. Cancelled midway,
// it returns the servers it finished, in order.
//
// The network stages for all servers run first and side by side: they are
// independent and mostly waiting. The tunnels then run one after another,
// each in a process of its own (see tunnel): two at once would share this
// computer's connection, and each node's window in its log would hold the
// other's traffic too.
func (r *Runner) Run(ctx context.Context, targets []*subscription.Target, done func(int, *Result)) []*Result {
	results := make([]*Result, len(targets))
	limit := make(chan struct{}, max(1, r.opts.Parallel))
	var wg sync.WaitGroup
	for i, target := range targets {
		results[i] = &Result{Target: target}
		if r.opts.RunID != "" {
			results[i].Marker = Marker(r.opts.RunID, i+1)
		}
		wg.Add(1)
		go func() {
			defer wg.Done()
			limit <- struct{}{}
			defer func() { <-limit }()
			r.network(ctx, results[i])
			if r.progress.Network != nil {
				r.progress.Network(i)
			}
		}()
	}
	wg.Wait()

	for i, result := range results {
		if ctx.Err() != nil {
			return results[:i]
		}
		if r.progress.Tunnel != nil {
			r.progress.Tunnel(i)
		}
		result.TunnelAt = time.Now()
		r.tunnel(ctx, result)
		result.TunnelTook = time.Since(result.TunnelAt)
		result.Took += result.TunnelTook
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

// Marker is the host a run asks for through server n. It ends in .invalid,
// which no resolver answers: the node logs the request as accepted, with the
// user it came from, and the lookup fails at once without leaving the node.
func Marker(runID string, n int) string {
	return fmt.Sprintf("vpncheck-%s-%02d.invalid", runID, n)
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
func Baseline(ctx context.Context, opts Options) ([]Step, Clock) {
	client := &http.Client{
		Transport:     &http.Transport{Proxy: nil, DisableKeepAlives: true},
		Timeout:       opts.Timeout,
		CheckRedirect: noRedirect,
	}
	var steps []Step
	var clock Clock
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
		sent := time.Now()
		status, body, took, err := get(ctx, client, opts.TraceURL)
		if err == nil && status == http.StatusOK {
			trace := parseTrace(body)
			clock = clockFrom(trace["ts"], sent, took)
			// The address is the customer's own; the country and the
			// Cloudflare city are enough to tell where the check ran from.
			steps = append(steps, Step{Name: "Откуда проверка", Status: OK, Took: took,
				Detail: fmt.Sprintf("страна %s, Cloudflare %s", orDash(trace["loc"]), orDash(trace["colo"]))})
		}
	}
	if name := ActiveTunnel(); name != "" {
		steps = append(steps, Step{Name: "Другой VPN", Status: Warn, Detail: fmt.Sprintf(
			"похоже, включён VPN (интерфейс %s): проверки пойдут через него, результаты будут неверными", name)})
	}
	return steps, clock
}

// Clock is how far this computer's clock is from Cloudflare's, so the times
// a report gives can be looked up in a node's log, which keeps real time.
type Clock struct {
	// Add to a local time to get the real one.
	Offset time.Duration
	Known  bool
}

// clockFrom reads the trace's ts=<unix seconds> against the middle of the
// request that fetched it: good to a fraction of a second, which is all the
// lookup needs.
func clockFrom(ts string, sent time.Time, took time.Duration) Clock {
	seconds, err := strconv.ParseFloat(ts, 64)
	if err != nil || seconds <= 0 {
		return Clock{}
	}
	actual := time.Unix(0, int64(seconds*float64(time.Second)))
	return Clock{Offset: actual.Sub(sent.Add(took / 2)).Round(100 * time.Millisecond), Known: true}
}

// ActiveTunnel names a network interface that looks like a running VPN
// client's TUN: Happ and Xray put theirs in 198.18.0.0/15, sing-box in
// 172.19.0.0/30 (the "Happ Tunnel" with DNS 172.19.0.2 in report 3).
func ActiveTunnel() string {
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
