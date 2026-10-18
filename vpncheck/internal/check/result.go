// Package check connects to one server at a time, the way a client app
// does, and records what each stage of the connection did.
//
// The stages are kept apart on purpose. "Does not work" has a dozen causes
// that look identical from inside a client -- DNS, a closed port, a REALITY
// target the node cannot reach, a wrong SNI, UDP cut by the carrier -- and
// the past incidents in this project were told apart only by reading which
// stage stopped. Each check here is one of those stages on its own.
package check

import (
	"time"

	"github.com/RuNick7/vpn-check/internal/subscription"
)

type Status int

const (
	OK Status = iota
	Warn
	Fail
	Skip
)

func (s Status) String() string {
	switch s {
	case OK:
		return "OK"
	case Warn:
		return "ВНИМАНИЕ"
	case Fail:
		return "ОШИБКА"
	}
	return "пропущено"
}

// Step is one stage of connecting: resolving the name, opening the port,
// the TLS handshake, a request through the tunnel.
type Step struct {
	Name   string
	Status Status
	Took   time.Duration
	Detail string
}

type Verdict int

const (
	Works Verdict = iota
	Partial
	Broken
)

func (v Verdict) String() string {
	switch v {
	case Works:
		return "РАБОТАЕТ"
	case Partial:
		return "ЧАСТИЧНО"
	}
	return "НЕ РАБОТАЕТ"
}

// Result is everything learned about one server.
type Result struct {
	Target  *subscription.Target
	Started time.Time
	Took    time.Duration
	Steps   []Step

	// When traffic went through the server, the part of the run its node
	// sees: the network stages before it run for every server at once.
	TunnelAt   time.Time
	TunnelTook time.Duration
	// The host asked for through this server so its node's log can be
	// searched for the run (see Marker), and whether the request was made.
	Marker     string
	MarkerSent bool

	// Round trips of the health-check request, each over a fresh connection,
	// so each includes the handshake -- what opening a site costs.
	Pings []time.Duration
	// What Cloudflare saw on the far side of the tunnel: ip, loc, colo, warp.
	Exit map[string]string
	// Download speed in megabits per second, when measured.
	Mbps float64

	Verdict Verdict
	// The decisive error in one line, from Xray's own log when it has one.
	Cause string
	Hints []string
	// Xray's log for this server alone, debug level.
	Log []string

	// Kept for the hints: the resolved addresses and the TLS handshake's
	// outcome, which the steps only describe in words.
	ips       []string
	tcpKind   errKind
	tlsKind   errKind
	curve     string
	certNames []string
}

func (r *Result) add(step Step) { r.Steps = append(r.Steps, step) }

func (r *Result) step(name string) *Step {
	for i := range r.Steps {
		if r.Steps[i].Name == name {
			return &r.Steps[i]
		}
	}
	return nil
}

// Best is the fastest ping, which is the fairest single number for a server.
func (r *Result) Best() time.Duration {
	var best time.Duration
	for _, ping := range r.Pings {
		if best == 0 || ping < best {
			best = ping
		}
	}
	return best
}
