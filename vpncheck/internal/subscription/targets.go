package subscription

import (
	"encoding/json"
	"fmt"
	"net"
	"strconv"
	"strings"
)

// Target is one server to check: a single proxy outbound exactly as the
// subscription gave it, plus whatever it dials through, and the name of every
// profile that uses it.
//
// A profile in the template is a balancer over several servers, and the same
// server appears in several profiles. Checking per outbound rather than per
// profile is what makes a report say which server failed, not which group
// contained one.
type Target struct {
	Profiles    []string
	Tag         string
	Protocol    string
	Address     string
	Port        int
	Network     string
	Security    string
	SNI         string
	Fingerprint string
	Flow        string
	// What tells two transports on one port apart: a gRPC service name, an
	// XHTTP path and mode, a WebSocket path.
	Detail string
	// Reached over UDP (Hysteria, mKCP): there is no TCP port to knock on,
	// and only the protocol itself can say whether the server answers.
	UDP bool

	Outbound map[string]any
	// Outbounds this one depends on, by tag -- a dialerProxy hop, typically a
	// freedom outbound that fragments the TLS hello.
	Chain []map[string]any
}

// Name is the first profile the server appears in.
func (t *Target) Name() string {
	if len(t.Profiles) == 0 {
		return t.Tag
	}
	return t.Profiles[0]
}

// Endpoint is host:port as written in the subscription.
func (t *Target) Endpoint() string {
	return net.JoinHostPort(t.Address, strconv.Itoa(t.Port))
}

// Kind summarises how the server is reached: "vless · grpc · reality".
func (t *Target) Kind() string {
	protocol := t.Protocol
	if protocol == "hysteria" {
		protocol = "hysteria2"
	}
	parts := []string{protocol}
	if t.Network != "" && t.Network != "hysteria" {
		parts = append(parts, t.Network)
	}
	if t.Security != "" && t.Security != "none" {
		parts = append(parts, t.Security)
	}
	if t.Flow != "" {
		parts = append(parts, strings.TrimPrefix(t.Flow, "xtls-rprx-"))
	}
	return strings.Join(parts, " · ")
}

var proxyProtocols = map[string]bool{
	"vless": true, "vmess": true, "trojan": true, "shadowsocks": true,
	"hysteria": true, "wireguard": true, "socks": true, "http": true,
}

// Targets lists every distinct server across the profiles, in the order the
// subscription first mentions them.
func Targets(profiles []Profile) []*Target {
	var targets []*Target
	seen := map[string]*Target{}
	for _, profile := range profiles {
		byTag := map[string]map[string]any{}
		for _, outbound := range profile.Outbounds {
			if tag := str(outbound, "tag"); tag != "" {
				byTag[tag] = outbound
			}
		}
		for _, outbound := range profile.Outbounds {
			if !proxyProtocols[str(outbound, "protocol")] {
				continue
			}
			chain := chainOf(outbound, byTag)
			key := identity(outbound, chain)
			if existing := seen[key]; existing != nil {
				if !contains(existing.Profiles, profile.Name) {
					existing.Profiles = append(existing.Profiles, profile.Name)
				}
				continue
			}
			target := describe(outbound)
			target.Profiles = []string{profile.Name}
			target.Chain = chain
			seen[key] = target
			targets = append(targets, target)
		}
	}
	return targets
}

// identity is what makes two outbounds the same server: everything but the
// tag, which the template numbers per profile (proxy, proxy-2, ...).
func identity(outbound map[string]any, chain []map[string]any) string {
	copied := make(map[string]any, len(outbound))
	for key, value := range outbound {
		if key != "tag" {
			copied[key] = value
		}
	}
	// encoding/json sorts map keys, so equal objects marshal equal.
	encoded, _ := json.Marshal([]any{copied, chain})
	return string(encoded)
}

// chainOf follows sockopt.dialerProxy and proxySettings.tag to the outbounds
// a server is dialled through. Without them its config would not load.
func chainOf(outbound map[string]any, byTag map[string]map[string]any) []map[string]any {
	var chain []map[string]any
	visited := map[string]bool{str(outbound, "tag"): true}
	current := outbound
	for depth := 0; depth < 4; depth++ {
		next := str(obj(obj(current, "streamSettings"), "sockopt"), "dialerProxy")
		if next == "" {
			next = str(obj(current, "proxySettings"), "tag")
		}
		hop, ok := byTag[next]
		if next == "" || !ok || visited[next] {
			break
		}
		visited[next] = true
		chain = append(chain, hop)
		current = hop
	}
	return chain
}

func describe(outbound map[string]any) *Target {
	settings := obj(outbound, "settings")
	stream := obj(outbound, "streamSettings")
	target := &Target{
		Tag:      str(outbound, "tag"),
		Protocol: str(outbound, "protocol"),
		Network:  str(stream, "network"),
		Security: str(stream, "security"),
		Outbound: outbound,
	}
	target.Address, target.Port, target.Flow = endpoint(target.Protocol, settings)

	switch target.Network {
	case "", "tcp":
		target.Network = "raw"
	case "splithttp":
		target.Network = "xhttp"
	}
	if target.Security == "" {
		target.Security = "none"
	}

	var alpn []any
	switch target.Security {
	case "reality":
		reality := obj(stream, "realitySettings")
		target.SNI, target.Fingerprint = str(reality, "serverName"), str(reality, "fingerprint")
	case "tls":
		tls := obj(stream, "tlsSettings")
		target.SNI, target.Fingerprint = str(tls, "serverName"), str(tls, "fingerprint")
		alpn, _ = tls["alpn"].([]any)
	}

	switch target.Network {
	case "grpc":
		target.Detail = "serviceName=" + str(obj(stream, "grpcSettings"), "serviceName")
	case "xhttp":
		xhttp := obj(stream, "xhttpSettings")
		if xhttp == nil {
			xhttp = obj(stream, "splithttpSettings")
		}
		target.Detail = strings.TrimSpace("path=" + str(xhttp, "path") + " mode=" + str(xhttp, "mode"))
	case "ws":
		target.Detail = "path=" + str(obj(stream, "wsSettings"), "path")
	case "httpupgrade":
		target.Detail = "path=" + str(obj(stream, "httpupgradeSettings"), "path")
	}

	target.UDP = target.Protocol == "hysteria" || target.Protocol == "wireguard" ||
		target.Network == "hysteria" || target.Network == "kcp" ||
		(target.Network == "xhttp" && containsAny(alpn, "h3"))
	return target
}

// endpoint finds the server address in any of the shapes Xray accepts: the
// flat one, vnext (VLESS/VMess), servers (Trojan/Shadowsocks), peers
// (WireGuard).
func endpoint(protocol string, settings map[string]any) (address string, port int, flow string) {
	if address = str(settings, "address"); address != "" {
		return address, num(settings, "port"), str(settings, "flow")
	}
	for _, key := range []string{"vnext", "servers"} {
		list, _ := settings[key].([]any)
		if len(list) == 0 {
			continue
		}
		server, _ := list[0].(map[string]any)
		users, _ := server["users"].([]any)
		if len(users) > 0 {
			if user, ok := users[0].(map[string]any); ok {
				flow = str(user, "flow")
			}
		}
		return str(server, "address"), num(server, "port"), flow
	}
	if protocol == "wireguard" {
		peers, _ := settings["peers"].([]any)
		if len(peers) > 0 {
			peer, _ := peers[0].(map[string]any)
			host, portText, err := net.SplitHostPort(str(peer, "endpoint"))
			if err == nil {
				port, _ = strconv.Atoi(portText)
				return host, port, ""
			}
		}
	}
	return "", 0, ""
}

func contains(list []string, value string) bool {
	for _, item := range list {
		if item == value {
			return true
		}
	}
	return false
}

func containsAny(list []any, value string) bool {
	for _, item := range list {
		if fmt.Sprint(item) == value {
			return true
		}
	}
	return false
}
