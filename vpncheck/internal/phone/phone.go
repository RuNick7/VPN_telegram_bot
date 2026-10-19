// Package phone is what the Android app tells vpncheck about the phone's
// connection. A process there sees little of it for itself: Android keeps
// no /etc/resolv.conf for Go's resolver to read, and lets an app list no
// network interfaces, so neither the system's DNS servers nor a running VPN
// can be found the way they are on a computer. The app's Java side asks the
// system and keeps the answer in a small file, rewritten whenever the
// connection changes; this reads it.
//
// The file is lines of key=value:
//
//	network=мобильная сеть, MegaFon
//	metered=1
//	vpn=1
//	dns=192.168.1.1,2a00:1fa0::1
package phone

import (
	"bufio"
	"context"
	"net"
	"os"
	"strings"
	"sync/atomic"

	"github.com/RuNick7/vpn-check/internal/check"
)

// FileEnv names the file, set by the Android app for the process it starts
// and inherited by every tunnel worker that process starts in turn.
const FileEnv = "VPNCHECK_PHONE"

// Fallback resolvers, for a connection whose DNS servers the system did not
// name: the one the subscription template resolves kairavpn.pro through,
// then Google's.
var fallbackDNS = []string{"77.88.8.8", "8.8.8.8"}

// Network is the phone's connection as the system describes it.
type Network struct {
	// How the system names it: "Wi-Fi", "мобильная сеть, MegaFon".
	Name string
	// Charged by the megabyte, as mobile data usually is.
	Metered bool
	// The system routes this app through a VPN.
	VPN bool
	// The connection's DNS servers, by address, with a port when it is not 53.
	DNS []string
}

// Read reads the file; a missing one is a connection nothing is known about.
func Read(path string) Network {
	var n Network
	file, err := os.Open(path)
	if err != nil {
		return n
	}
	defer file.Close()
	lines := bufio.NewScanner(file)
	for lines.Scan() {
		key, value, ok := strings.Cut(strings.TrimSpace(lines.Text()), "=")
		if !ok {
			continue
		}
		switch key {
		case "network":
			n.Name = value
		case "metered":
			n.Metered = value == "1"
		case "vpn":
			n.VPN = value == "1"
		case "dns":
			for _, server := range strings.Split(value, ",") {
				if server = strings.TrimSpace(server); server != "" {
					n.DNS = append(n.DNS, server)
				}
			}
		}
	}
	return n
}

// Use makes this process take its network from the file at path: the
// system resolver asks the phone's DNS servers, and the check learns of a
// VPN and of the connection's name from the system. Call it first thing in
// main, before anything resolves a name.
func Use(path string) {
	// net.DefaultResolver is changed in place, not replaced: Xray keeps a
	// copy of the pointer from its own start-up.
	var turn atomic.Uint32
	net.DefaultResolver.PreferGo = true
	net.DefaultResolver.Dial = func(ctx context.Context, network, _ string) (net.Conn, error) {
		// Go's resolver asks its two default servers in turn when one
		// does not answer; each turn here is the next of the phone's.
		servers := Read(path).DNS
		if len(servers) == 0 {
			servers = fallbackDNS
		}
		server := servers[int(turn.Add(1)-1)%len(servers)]
		if _, _, err := net.SplitHostPort(server); err != nil {
			server = net.JoinHostPort(server, "53")
		}
		var d net.Dialer
		return d.DialContext(ctx, network, server)
	}
	check.SystemVPN = func() bool { return Read(path).VPN }
	check.SystemNetwork = func() string { return Read(path).Name }
}
