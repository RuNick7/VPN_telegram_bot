// Package nodes asks the vpncheck-agent on each node for its side of a run,
// the way admin_bot does for a customer's report -- so an operator running
// vpncheck can read what every node logged next to what the client saw.
package nodes

import (
	"bytes"
	"context"
	"crypto/sha256"
	"crypto/tls"
	"crypto/x509"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"regexp"
	"strings"
	"sync"
	"time"

	"github.com/RuNick7/vpn-check/internal/nodelog"
)

// Agent is one entry of NODE_LOG_AGENTS: name=https://token@host:port#sha256.
type Agent struct {
	Name        string
	URL         string
	Token       string
	Fingerprint []byte
}

var separators = regexp.MustCompile(`[\s,;]+`)

// Parse reads NODE_LOG_AGENTS as the agents print it. An entry that does not
// parse is returned as an error naming it -- by name and position, never with
// its token -- and left out.
func Parse(raw string) ([]Agent, []error) {
	var agents []Agent
	var errs []error
	for i, entry := range separators.Split(strings.TrimSpace(raw), -1) {
		if entry == "" {
			continue
		}
		name, rest, _ := strings.Cut(entry, "=")
		agent, ok := parseURL(name, rest)
		if !ok {
			errs = append(errs, fmt.Errorf("NODE_LOG_AGENTS: запись %d (%s) не в виде name=https://token@host:port#sha256", i+1, orQuestion(name)))
			continue
		}
		agents = append(agents, agent)
	}
	return agents, errs
}

func parseURL(name, raw string) (Agent, bool) {
	u, err := url.Parse(raw)
	if err != nil || name == "" || u.Scheme != "https" || u.User == nil || u.User.Username() == "" || u.Port() == "" {
		return Agent{}, false
	}
	fingerprint, err := hex.DecodeString(u.Fragment)
	if err != nil || len(fingerprint) != sha256.Size {
		return Agent{}, false
	}
	return Agent{Name: name, URL: "https://" + u.Host, Token: u.User.Username(), Fingerprint: fingerprint}, true
}

func orQuestion(s string) string {
	if s == "" {
		return "?"
	}
	return s
}

// Answer is one agent's reply, or why there is none.
type Answer struct {
	Agent    Agent
	Response *nodelog.Response
	Err      error
}

var ErrFingerprint = errors.New("отвечает не тот сертификат: агент переустановлен или это не он — обновите его строку в NODE_LOG_AGENTS")

// client reaches one agent through its own certificate and nothing else:
// the agent's certificate is self-signed, so instead of a CA the pinned
// fingerprint is what decides.
func client(agent Agent, timeout time.Duration) *http.Client {
	return &http.Client{
		Timeout: timeout,
		Transport: &http.Transport{
			Proxy: nil,
			TLSClientConfig: &tls.Config{
				MinVersion: tls.VersionTLS13,
				// Not a skipped check: VerifyPeerCertificate below replaces
				// the CA chain with the pin, and refuses anything else.
				InsecureSkipVerify: true,
				VerifyPeerCertificate: func(raw [][]byte, _ [][]*x509.Certificate) error {
					if len(raw) == 0 {
						return ErrFingerprint
					}
					sum := sha256.Sum256(raw[0])
					if !bytes.Equal(sum[:], agent.Fingerprint) {
						return ErrFingerprint
					}
					return nil
				},
			},
		},
	}
}

// Ask sends the query to every agent at once.
func Ask(ctx context.Context, agents []Agent, query nodelog.Query, timeout time.Duration) []Answer {
	answers := make([]Answer, len(agents))
	body, _ := json.Marshal(query)
	var wg sync.WaitGroup
	for i, agent := range agents {
		wg.Add(1)
		go func() {
			defer wg.Done()
			response, err := ask(ctx, agent, body, timeout)
			answers[i] = Answer{Agent: agent, Response: response, Err: err}
		}()
	}
	wg.Wait()
	return answers
}

func ask(ctx context.Context, agent Agent, body []byte, timeout time.Duration) (*nodelog.Response, error) {
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, agent.URL+"/v1/search", bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Authorization", "Bearer "+agent.Token)
	req.Header.Set("Content-Type", "application/json")
	resp, err := client(agent, timeout).Do(req)
	if err != nil {
		if errors.Is(err, ErrFingerprint) {
			return nil, ErrFingerprint
		}
		return nil, err
	}
	defer resp.Body.Close()
	data, err := io.ReadAll(io.LimitReader(resp.Body, 64<<20))
	if err != nil {
		return nil, err
	}
	if resp.StatusCode != http.StatusOK {
		return nil, fmt.Errorf("HTTP %d: %s", resp.StatusCode, strings.TrimSpace(string(data[:min(len(data), 200)])))
	}
	var response nodelog.Response
	if err := json.Unmarshal(data, &response); err != nil {
		return nil, err
	}
	return &response, nil
}
