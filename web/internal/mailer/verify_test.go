package mailer

import (
	"bufio"
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/tls"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/base64"
	"math/big"
	"net"
	"strconv"
	"strings"
	"testing"
	"time"
)

// Verify() is what an operator runs while a hosting provider is still opening
// the outbound port, and what tells them their API key is right before they
// send anything. It talks to a real TLS socket, so it is tested against one.

// fakeSMTP is a server that speaks just enough SMTP to authenticate.
type fakeSMTP struct {
	addr        string
	rootCAs     *x509.CertPool
	acceptAuth  bool
	offerAuth   bool
	gotUsername string
	gotPassword string
}

func startFakeSMTP(t *testing.T, acceptAuth, offerAuth bool) *fakeSMTP {
	t.Helper()

	cert, pool := selfSigned(t)
	listener, err := tls.Listen("tcp", "127.0.0.1:0",
		&tls.Config{Certificates: []tls.Certificate{cert}, MinVersion: tls.VersionTLS12})
	if err != nil {
		t.Fatalf("listen: %v", err)
	}
	t.Cleanup(func() { listener.Close() })

	server := &fakeSMTP{
		addr:       listener.Addr().String(),
		rootCAs:    pool,
		acceptAuth: acceptAuth,
		offerAuth:  offerAuth,
	}

	go func() {
		for {
			conn, err := listener.Accept()
			if err != nil {
				return
			}
			go server.handle(conn)
		}
	}()
	return server
}

func (s *fakeSMTP) handle(conn net.Conn) {
	defer conn.Close()
	reader := bufio.NewReader(conn)
	write := func(line string) { conn.Write([]byte(line + "\r\n")) }

	write("220 fake.test ESMTP")
	for {
		line, err := reader.ReadString('\n')
		if err != nil {
			return
		}
		command := strings.ToUpper(strings.TrimSpace(line))

		switch {
		case strings.HasPrefix(command, "EHLO"), strings.HasPrefix(command, "HELO"):
			if s.offerAuth {
				write("250-fake.test")
				write("250 AUTH PLAIN LOGIN")
			} else {
				write("250 fake.test")
			}

		case strings.HasPrefix(command, "AUTH PLAIN"):
			// The payload is \x00user\x00pass, base64-encoded.
			if _, encoded, ok := strings.Cut(strings.TrimSpace(line), "AUTH PLAIN "); ok {
				if raw, err := base64.StdEncoding.DecodeString(strings.TrimSpace(encoded)); err == nil {
					if parts := strings.Split(string(raw), "\x00"); len(parts) == 3 {
						s.gotUsername, s.gotPassword = parts[1], parts[2]
					}
				}
			}
			if s.acceptAuth {
				write("235 2.7.0 Authentication successful")
			} else {
				write("535 5.7.8 Error: authentication failed")
			}

		case strings.HasPrefix(command, "QUIT"):
			write("221 Bye")
			return

		default:
			write("250 OK")
		}
	}
}

func selfSigned(t *testing.T) (tls.Certificate, *x509.CertPool) {
	t.Helper()

	key, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		t.Fatal(err)
	}
	template := &x509.Certificate{
		SerialNumber:          big.NewInt(1),
		Subject:               pkix.Name{CommonName: "127.0.0.1"},
		NotBefore:             time.Now().Add(-time.Hour),
		NotAfter:              time.Now().Add(time.Hour),
		KeyUsage:              x509.KeyUsageDigitalSignature | x509.KeyUsageCertSign,
		ExtKeyUsage:           []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth},
		IPAddresses:           []net.IP{net.ParseIP("127.0.0.1")},
		IsCA:                  true,
		BasicConstraintsValid: true,
	}
	der, err := x509.CreateCertificate(rand.Reader, template, template, &key.PublicKey, key)
	if err != nil {
		t.Fatal(err)
	}
	parsed, err := x509.ParseCertificate(der)
	if err != nil {
		t.Fatal(err)
	}
	pool := x509.NewCertPool()
	pool.AddCert(parsed)
	return tls.Certificate{Certificate: [][]byte{der}, PrivateKey: key, Leaf: parsed}, pool
}

func mailerFor(t *testing.T, server *fakeSMTP, username, password string) *Mailer {
	t.Helper()
	host, port, err := net.SplitHostPort(server.addr)
	if err != nil {
		t.Fatal(err)
	}
	portNumber, err := strconv.Atoi(port)
	if err != nil {
		t.Fatal(err)
	}
	m, err := New(Config{
		Host: host, Port: portNumber, Username: username, Password: password,
		From: "noreply@kairavpn.pro", StartTLS: false, // implicit TLS, like port 465
	})
	if err != nil {
		t.Fatal(err)
	}
	m.rootCAs = server.rootCAs
	return m
}

func TestVerifySucceedsAgainstARealTLSServer(t *testing.T) {
	server := startFakeSMTP(t, true, true)
	m := mailerFor(t, server, "kaira", "an-api-key")

	if err := m.Verify(); err != nil {
		t.Fatalf("Verify: %v", err)
	}
	// The credentials must actually be presented -- a Verify that connected and
	// hung up without authenticating would report success on a wrong key.
	if server.gotUsername != "kaira" || server.gotPassword != "an-api-key" {
		t.Errorf("server saw %q/%q, want kaira/an-api-key", server.gotUsername, server.gotPassword)
	}
}

func TestVerifyReportsRejectedCredentials(t *testing.T) {
	server := startFakeSMTP(t, false, true)
	m := mailerFor(t, server, "kaira", "wrong-key")

	err := m.Verify()
	if err == nil {
		t.Fatal("Verify accepted a rejected key")
	}
	// diagnose() keys off this text to tell the operator to check the API key.
	if !strings.Contains(err.Error(), "535") {
		t.Errorf("error %q does not carry the server's reply", err)
	}
}

func TestVerifySkipsAuthWhenNoUsernameIsSet(t *testing.T) {
	// A relay on a private network needs no credentials, and offering none is
	// different from offering the wrong ones.
	server := startFakeSMTP(t, false, false)
	m := mailerFor(t, server, "", "")

	if err := m.Verify(); err != nil {
		t.Fatalf("Verify: %v", err)
	}
	if server.gotUsername != "" {
		t.Errorf("credentials were sent anyway: %q", server.gotUsername)
	}
}

func TestVerifyFailsFastOnAClosedPort(t *testing.T) {
	// What a blocked outbound port looks like. It must return, not hang.
	listener, err := net.Listen("tcp", "127.0.0.1:0")
	if err != nil {
		t.Fatal(err)
	}
	addr := listener.Addr().String()
	listener.Close() // nothing is listening now

	host, port, _ := net.SplitHostPort(addr)
	portNumber, err := strconv.Atoi(port)
	if err != nil {
		t.Fatal(err)
	}
	m, err := New(Config{Host: host, Port: portNumber, From: "a@b.c", StartTLS: true})
	if err != nil {
		t.Fatal(err)
	}

	done := make(chan error, 1)
	go func() { done <- m.Verify() }()
	select {
	case err := <-done:
		if err == nil {
			t.Fatal("Verify succeeded against a closed port")
		}
	case <-time.After(20 * time.Second):
		t.Fatal("Verify hung on a closed port")
	}
}

func TestVerifyRefusesAnUntrustedCertificate(t *testing.T) {
	// Without the test's root pool the self-signed certificate must be
	// rejected -- which is the proof that production, where rootCAs is nil,
	// validates against the system roots rather than accepting anything.
	server := startFakeSMTP(t, true, true)
	host, port, _ := net.SplitHostPort(server.addr)
	portNumber, err := strconv.Atoi(port)
	if err != nil {
		t.Fatal(err)
	}
	m, err := New(Config{Host: host, Port: portNumber, From: "a@b.c", StartTLS: false})
	if err != nil {
		t.Fatal(err)
	}

	if err := m.Verify(); err == nil {
		t.Fatal("an unknown certificate authority was accepted")
	}
}
