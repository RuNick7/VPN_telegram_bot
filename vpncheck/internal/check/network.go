package check

import (
	"context"
	"crypto/tls"
	"crypto/x509"
	"errors"
	"fmt"
	"net"
	"os"
	"slices"
	"strconv"
	"strings"
	"sync"
	"syscall"
	"time"
)

// Step names, also what the reports print.
const (
	StepDNS    = "DNS"
	StepTCP    = "TCP-порт"
	StepTLS    = "TLS"
	StepTunnel = "Туннель"
)

type lookup struct {
	name string
	ips  []string
	err  error
	took time.Duration
}

// probeDNS resolves the server's name with the system resolver -- what Xray
// uses to dial -- and, for comparison, with public resolvers asked directly.
// The comparison is what tells "the server is down" from "the provider's DNS
// lies about it".
func probeDNS(ctx context.Context, host string, resolvers []string, timeout time.Duration) (Step, []string) {
	if ip := net.ParseIP(host); ip != nil {
		return Step{Name: StepDNS, Status: Skip, Detail: "адрес указан IP-адресом"}, []string{host}
	}

	lookups := make([]lookup, 1+len(resolvers))
	var wg sync.WaitGroup
	for i := range lookups {
		wg.Add(1)
		go func() {
			defer wg.Done()
			resolver, name := net.DefaultResolver, "система"
			if i > 0 {
				server := resolvers[i-1]
				name = strings.TrimSuffix(server, ":53")
				resolver = &net.Resolver{PreferGo: true, Dial: func(ctx context.Context, _, _ string) (net.Conn, error) {
					var d net.Dialer
					return d.DialContext(ctx, "udp", server)
				}}
			}
			lctx, cancel := context.WithTimeout(ctx, timeout)
			defer cancel()
			started := time.Now()
			addrs, err := resolver.LookupIP(lctx, "ip", host)
			lookups[i] = lookup{name: name, err: err, took: time.Since(started)}
			for _, addr := range addrs {
				lookups[i].ips = append(lookups[i].ips, addr.String())
			}
			sortIPv4First(lookups[i].ips)
		}()
	}
	wg.Wait()

	var parts []string
	for _, l := range lookups {
		if l.err != nil {
			parts = append(parts, fmt.Sprintf("%s: ошибка (%s)", l.name, shortError(l.err)))
		} else {
			parts = append(parts, fmt.Sprintf("%s: %s (%s)", l.name, strings.Join(l.ips, ", "), ms(l.took)))
		}
	}
	step := Step{Name: StepDNS, Took: lookups[0].took, Detail: strings.Join(parts, "; ")}

	system := lookups[0]
	if system.err != nil {
		step.Status = Fail
		// Still hand on whatever a public resolver found, so the port check
		// can say whether the server itself is reachable.
		for _, l := range lookups[1:] {
			if l.err == nil && len(l.ips) > 0 {
				return step, l.ips
			}
		}
		return step, nil
	}
	step.Status = OK
	for _, l := range lookups[1:] {
		if l.err == nil && len(l.ips) > 0 && !overlaps(system.ips, l.ips) {
			step.Status = Warn
		}
	}
	return step, system.ips
}

// probeTCP opens the server's port, trying the next address if the first
// fails, the way a dialer would.
func probeTCP(ctx context.Context, ips []string, port int, timeout time.Duration) (Step, errKind) {
	step := Step{Name: StepTCP, Status: Fail}
	if len(ips) == 0 {
		step.Status, step.Detail = Skip, "нет IP-адреса"
		return step, ""
	}
	var failures []string
	var kind errKind
	for _, ip := range ips[:min(2, len(ips))] {
		address := net.JoinHostPort(ip, strconv.Itoa(port))
		dialer := net.Dialer{Timeout: timeout}
		started := time.Now()
		conn, err := dialer.DialContext(ctx, "tcp", address)
		if err == nil {
			conn.Close()
			step.Status, step.Took = OK, time.Since(started)
			step.Detail = fmt.Sprintf("%s — соединение за %s", address, ms(step.Took))
			return step, ""
		}
		step.Took = time.Since(started)
		kind = netErrorKind(err)
		failures = append(failures, fmt.Sprintf("%s — %s", address, describeNetError(err)))
	}
	step.Detail = strings.Join(failures, "; ")
	return step, kind
}

// probeTLS shakes hands with the server under the SNI the client uses,
// without the client's key, and notes who answered.
//
// For REALITY that is the point: a REALITY server hands an unknown client
// through to its target, so this sees the target's own certificate -- and a
// handshake that never completes means the node cannot reach its target,
// the failure us1 had. For plain TLS it checks the certificate covers the
// SNI, the failure de5's Hysteria had.
type handshake struct {
	step  Step
	kind  errKind
	curve string
	names []string
}

func probeTLS(ctx context.Context, ip string, port int, sni string, security string, timeout time.Duration) handshake {
	step := Step{Name: StepTLS}
	if sni == "" {
		sni = ip
	}
	dialer := tls.Dialer{
		NetDialer: &net.Dialer{Timeout: timeout},
		Config: &tls.Config{
			ServerName:         sni,
			InsecureSkipVerify: true, // judged below, after seeing what came back
			NextProtos:         []string{"h2", "http/1.1"},
			MinVersion:         tls.VersionTLS12,
		},
	}
	hctx, cancel := context.WithTimeout(ctx, timeout)
	defer cancel()
	started := time.Now()
	raw, err := dialer.DialContext(hctx, "tcp", net.JoinHostPort(ip, strconv.Itoa(port)))
	step.Took = time.Since(started)
	if err != nil {
		step.Status = Fail
		step.Detail = fmt.Sprintf("SNI %s — %s", sni, describeNetError(err))
		return handshake{step: step, kind: netErrorKind(err)}
	}
	conn := raw.(*tls.Conn)
	defer conn.Close()

	state := conn.ConnectionState()
	curve := state.CurveID.String()
	parts := []string{
		"SNI " + sni,
		tlsVersion(state.Version),
		curve,
	}
	if state.NegotiatedProtocol != "" {
		parts = append(parts, "ALPN "+state.NegotiatedProtocol)
	}
	var names []string
	step.Status = OK
	if len(state.PeerCertificates) > 0 {
		leaf := state.PeerCertificates[0]
		names = certNames(leaf)
		issuer := leaf.Issuer.CommonName
		if issuer == "" && len(leaf.Issuer.Organization) > 0 {
			issuer = leaf.Issuer.Organization[0]
		}
		parts = append(parts, fmt.Sprintf("сертификат на %s (выдан %s, до %s)",
			strings.Join(names, ", "), orDash(issuer), leaf.NotAfter.Format("2006-01-02")))
		if leaf.VerifyHostname(sni) != nil {
			parts = append(parts, "сертификат не покрывает SNI")
			step.Status = Warn
		} else if security == "tls" {
			if err := verifyChain(state.PeerCertificates, sni); err != nil {
				parts = append(parts, "цепочка не проверяется: "+shortError(err))
				step.Status = Warn
			}
		}
	}
	step.Detail = fmt.Sprintf("%s — за %s", strings.Join(parts, ", "), ms(step.Took))
	return handshake{step: step, curve: curve, names: names}
}

func verifyChain(chain []*x509.Certificate, name string) error {
	intermediates := x509.NewCertPool()
	for _, cert := range chain[1:] {
		intermediates.AddCert(cert)
	}
	_, err := chain[0].Verify(x509.VerifyOptions{DNSName: name, Intermediates: intermediates})
	return err
}

func certNames(cert *x509.Certificate) []string {
	names := slices.Clone(cert.DNSNames)
	if len(names) == 0 && cert.Subject.CommonName != "" {
		names = []string{cert.Subject.CommonName}
	}
	if len(names) > 4 {
		names = append(names[:4], fmt.Sprintf("и ещё %d", len(cert.DNSNames)-4))
	}
	return names
}

func tlsVersion(version uint16) string {
	switch version {
	case tls.VersionTLS13:
		return "TLS 1.3"
	case tls.VersionTLS12:
		return "TLS 1.2"
	}
	return fmt.Sprintf("TLS 0x%04x", version)
}

// describeNetError names a dial failure the way the hints need it named:
// refused, timed out, reset or unreachable, with the raw error after.
func describeNetError(err error) string {
	return fmt.Sprintf("%s (%s)", netErrorKind(err), shortError(err))
}

type errKind string

const (
	kindRefused     errKind = "соединение отклонено"
	kindReset       errKind = "соединение сброшено"
	kindUnreachable errKind = "сеть недоступна"
	kindTimeout     errKind = "нет ответа"
	kindClosed      errKind = "соединение закрыто сервером"
	kindOther       errKind = "ошибка"
)

// netErrorKind sorts a dial error. The text checks back up the errno ones:
// Windows reports these as WSA codes that syscall's constants do not match.
func netErrorKind(err error) errKind {
	switch {
	case errors.Is(err, syscall.ECONNREFUSED):
		return kindRefused
	case errors.Is(err, syscall.ECONNRESET):
		return kindReset
	case errors.Is(err, syscall.ENETUNREACH), errors.Is(err, syscall.EHOSTUNREACH):
		return kindUnreachable
	case errors.Is(err, context.DeadlineExceeded), errors.Is(err, os.ErrDeadlineExceeded), isTimeout(err):
		return kindTimeout
	}
	text := strings.ToLower(err.Error())
	switch {
	case strings.Contains(text, "refused"):
		return kindRefused
	case strings.Contains(text, "reset"), strings.Contains(text, "forcibly closed"):
		return kindReset
	case strings.Contains(text, "eof"):
		return kindClosed
	case strings.Contains(text, "unreachable"):
		return kindUnreachable
	}
	return kindOther
}

func isTimeout(err error) bool {
	var netErr net.Error
	return errors.As(err, &netErr) && netErr.Timeout()
}

// shortError trims Go's "dial tcp 1.2.3.4:443: connect:" prefixes down to
// the part that says what happened.
func shortError(err error) string {
	text := err.Error()
	if index := strings.LastIndex(text, ": "); index >= 0 {
		if tail := text[index+2:]; len(tail) >= 6 {
			return tail
		}
	}
	return text
}

func ms(d time.Duration) string {
	if d < time.Millisecond {
		return "<1 мс"
	}
	return strconv.FormatInt(d.Milliseconds(), 10) + " мс"
}

func overlaps(a, b []string) bool {
	for _, x := range a {
		if slices.Contains(b, x) {
			return true
		}
	}
	return false
}

func sortIPv4First(ips []string) {
	slices.SortStableFunc(ips, func(a, b string) int {
		a4, b4 := strings.Contains(a, "."), strings.Contains(b, ".")
		switch {
		case a4 && !b4:
			return -1
		case b4 && !a4:
			return 1
		}
		return 0
	})
}
