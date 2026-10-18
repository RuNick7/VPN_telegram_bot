// vpncheck-agent runs on a node and answers one question from admin_bot:
// what did this node's Xray log while a customer's vpncheck run went through
// it (see internal/nodelog).
//
// The logs it reads hold every customer's addresses, so it answers only over
// TLS and only to the token it made on first start. The certificate is its
// own, self-signed; admin_bot pins its fingerprint instead of trusting a CA,
// which is why one line -- printed at start and by -print -- is all the bot
// needs to reach it.
package main

import (
	"context"
	"crypto/ecdsa"
	"crypto/elliptic"
	"crypto/rand"
	"crypto/sha256"
	"crypto/subtle"
	"crypto/tls"
	"crypto/x509"
	"crypto/x509/pkix"
	"encoding/base64"
	"encoding/hex"
	"encoding/json"
	"encoding/pem"
	"errors"
	"flag"
	"fmt"
	"log"
	"math/big"
	"net"
	"net/http"
	"os"
	"os/signal"
	"path/filepath"
	"strings"
	"sync"
	"syscall"
	"time"

	"github.com/RuNick7/vpn-check/internal/nodelog"
)

var version = "dev"

type listFlag []string

func (l *listFlag) String() string     { return strings.Join(*l, ", ") }
func (l *listFlag) Set(v string) error { *l = append(*l, v); return nil }

func main() {
	var logs listFlag
	listen := flag.String("listen", ":7443", "адрес и порт, на которых ждать admin_bot")
	data := flag.String("data", "/var/lib/vpncheck-agent", "папка для ключа, сертификата и токена")
	flag.Var(&logs, "log", "лог Xray ноды (можно несколько раз); по умолчанию /var/log/remnanode/access.log и error.log")
	zone := flag.String("tz", "UTC", "часовой пояс, в котором Xray пишет время в лог")
	name := flag.String("name", "", "имя ноды в отчётах (по умолчанию имя хоста)")
	public := flag.String("public", "", "адрес, по которому admin_bot достучится до агента (по умолчанию имя ноды)")
	printOnly := flag.Bool("print", false, "показать строку для NODE_LOG_AGENTS и выйти")
	flag.Parse()

	if len(logs) == 0 {
		logs = listFlag{"/var/log/remnanode/access.log", "/var/log/remnanode/error.log"}
	}
	loc, err := time.LoadLocation(*zone)
	if err != nil {
		log.Fatalf("часовой пояс %q: %v", *zone, err)
	}
	if *name == "" {
		*name, _ = os.Hostname()
	}
	if *public == "" {
		*public = *name
	}
	creds, err := loadOrCreate(*data)
	if err != nil {
		log.Fatal(err)
	}
	_, port, err := net.SplitHostPort(*listen)
	if err != nil {
		log.Fatalf("-listen %q: %v", *listen, err)
	}
	line := connectionLine(*name, creds, net.JoinHostPort(*public, port))
	if *printOnly {
		fmt.Println(line)
		return
	}

	agent := &agent{name: *name, logs: logs, loc: loc, token: creds.token}
	server := &http.Server{
		Addr:              *listen,
		Handler:           agent.routes(),
		TLSConfig:         &tls.Config{Certificates: []tls.Certificate{creds.cert}, MinVersion: tls.VersionTLS13},
		ReadHeaderTimeout: 10 * time.Second,
		ReadTimeout:       30 * time.Second,
		WriteTimeout:      2 * time.Minute,
	}
	log.Printf("vpncheck-agent %s: нода %s, логи %s, пояс %s", version, *name, strings.Join(logs, ", "), *zone)
	log.Printf("строка для NODE_LOG_AGENTS в .env admin_bot:\n%s", line)
	// Said at start, so a log the agent cannot read shows up in the journal
	// on install rather than as empty answers later.
	for _, file := range openable(logs) {
		if file.Error != "" {
			log.Printf("ВНИМАНИЕ: не читается %s", file.Error)
		}
	}

	ctx, stop := signal.NotifyContext(context.Background(), os.Interrupt, syscall.SIGTERM)
	defer stop()
	go func() {
		<-ctx.Done()
		shutdown, cancel := context.WithTimeout(context.Background(), 5*time.Second)
		defer cancel()
		_ = server.Shutdown(shutdown)
	}()
	if err := server.ListenAndServeTLS("", ""); err != nil && !errors.Is(err, http.ErrServerClosed) {
		log.Fatal(err)
	}
}

// connectionLine is the NODE_LOG_AGENTS entry for this agent: its name, the
// token as the URL's user, and the certificate's fingerprint as the fragment.
func connectionLine(name string, creds *credentials, hostPort string) string {
	return fmt.Sprintf("%s=https://%s@%s#%s", name, creds.token, hostPort, creds.fingerprint)
}

type agent struct {
	name  string
	logs  []string
	loc   *time.Location
	token string
	// One search at a time: each reads whole log files, and two at once
	// would only make both slower on a node that is also carrying traffic.
	searching sync.Mutex
}

func (a *agent) routes() http.Handler {
	mux := http.NewServeMux()
	mux.HandleFunc("POST /v1/search", a.authorized(a.search))
	mux.HandleFunc("GET /v1/health", a.authorized(a.health))
	return mux
}

// failedAuthDelay slows every wrong token down, so it cannot be guessed at
// any useful rate.
var failedAuthDelay = time.Second

func (a *agent) authorized(next http.HandlerFunc) http.HandlerFunc {
	return func(w http.ResponseWriter, r *http.Request) {
		got, ok := strings.CutPrefix(r.Header.Get("Authorization"), "Bearer ")
		if !ok || subtle.ConstantTimeCompare([]byte(got), []byte(a.token)) != 1 {
			time.Sleep(failedAuthDelay)
			http.Error(w, "unauthorized", http.StatusUnauthorized)
			return
		}
		next(w, r)
	}
}

func (a *agent) search(w http.ResponseWriter, r *http.Request) {
	var query nodelog.Query
	decoder := json.NewDecoder(http.MaxBytesReader(w, r.Body, 64<<10))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&query); err != nil {
		http.Error(w, "bad request", http.StatusBadRequest)
		return
	}
	a.searching.Lock()
	sections, files, err := nodelog.Search(a.logs, a.loc, query)
	a.searching.Unlock()
	if err != nil {
		http.Error(w, err.Error(), http.StatusBadRequest)
		return
	}
	writeJSON(w, nodelog.Response{Node: a.name, Files: files, Sections: sections})
}

// health says which logs the agent can read, for checking an install.
func (a *agent) health(w http.ResponseWriter, _ *http.Request) {
	writeJSON(w, nodelog.Response{Node: a.name, Files: openable(a.logs)})
}

func openable(paths []string) []nodelog.File {
	files := make([]nodelog.File, 0, len(paths))
	for _, path := range paths {
		file := nodelog.File{Path: path}
		if f, err := os.Open(path); err != nil {
			file.Error = err.Error()
		} else {
			if info, err := f.Stat(); err == nil {
				file.Size = info.Size()
			}
			f.Close()
		}
		files = append(files, file)
	}
	return files
}

func writeJSON(w http.ResponseWriter, value any) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(value)
}

type credentials struct {
	token       string
	cert        tls.Certificate
	fingerprint string
}

// loadOrCreate keeps the token and the certificate across restarts: the
// line admin_bot holds stays valid until the data directory is wiped.
func loadOrCreate(dir string) (*credentials, error) {
	if err := os.MkdirAll(dir, 0o700); err != nil {
		return nil, err
	}
	tokenPath := filepath.Join(dir, "token")
	certPath, keyPath := filepath.Join(dir, "cert.pem"), filepath.Join(dir, "key.pem")

	token, err := os.ReadFile(tokenPath)
	if errors.Is(err, os.ErrNotExist) {
		raw := make([]byte, 32)
		_, _ = rand.Read(raw)
		token = []byte(base64.RawURLEncoding.EncodeToString(raw))
		err = os.WriteFile(tokenPath, token, 0o600)
	}
	if err != nil {
		return nil, err
	}

	if _, err := os.Stat(certPath); errors.Is(err, os.ErrNotExist) {
		if err := newCertificate(certPath, keyPath); err != nil {
			return nil, err
		}
	}
	cert, err := tls.LoadX509KeyPair(certPath, keyPath)
	if err != nil {
		return nil, err
	}
	sum := sha256.Sum256(cert.Certificate[0])
	return &credentials{
		token:       strings.TrimSpace(string(token)),
		cert:        cert,
		fingerprint: hex.EncodeToString(sum[:]),
	}, nil
}

func newCertificate(certPath, keyPath string) error {
	key, err := ecdsa.GenerateKey(elliptic.P256(), rand.Reader)
	if err != nil {
		return err
	}
	serial, _ := rand.Int(rand.Reader, new(big.Int).Lsh(big.NewInt(1), 63))
	template := &x509.Certificate{
		SerialNumber: serial,
		Subject:      pkix.Name{CommonName: "vpncheck-agent"},
		NotBefore:    time.Now().Add(-time.Hour),
		// Pinned, not validated against a CA: its lifetime protects nothing,
		// and an expiry would only break the bot one day years from now.
		NotAfter:    time.Now().AddDate(30, 0, 0),
		KeyUsage:    x509.KeyUsageDigitalSignature,
		ExtKeyUsage: []x509.ExtKeyUsage{x509.ExtKeyUsageServerAuth},
	}
	der, err := x509.CreateCertificate(rand.Reader, template, template, &key.PublicKey, key)
	if err != nil {
		return err
	}
	keyDER, err := x509.MarshalECPrivateKey(key)
	if err != nil {
		return err
	}
	if err := os.WriteFile(keyPath, pem.EncodeToMemory(&pem.Block{Type: "EC PRIVATE KEY", Bytes: keyDER}), 0o600); err != nil {
		return err
	}
	return os.WriteFile(certPath, pem.EncodeToMemory(&pem.Block{Type: "CERTIFICATE", Bytes: der}), 0o644)
}
