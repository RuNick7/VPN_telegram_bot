// Package ticket sends a report into a support ticket, with the one-time
// code the customer got from the bot after agreeing to it.
//
// The code is the whole authorisation: it names one ticket, works for a few
// days, and stops working once a report has been attached. vpncheck holds
// no account and no session; nothing it sends can reach any ticket but the
// one the customer agreed for.
package ticket

import (
	"bytes"
	"context"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"mime/multipart"
	"net/http"
	"os"
	"path/filepath"
	"strings"
	"time"
)

// Alphabet is the code's: no 0/O or 1/I to misread from a phone screen.
const Alphabet = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"

// CodeLen is how many characters of Alphabet a code has, shown in groups
// of four.
const CodeLen = 12

// NormalizeCode reads a code the way a person might type it -- lower case,
// with or without dashes and spaces -- and returns it as shown, XXXX-XXXX-XXXX.
func NormalizeCode(text string) (string, bool) {
	var b strings.Builder
	for _, c := range strings.ToUpper(strings.TrimSpace(text)) {
		switch {
		case c == '-' || c == ' ':
		case strings.ContainsRune(Alphabet, c):
			b.WriteRune(c)
		default:
			return "", false
		}
	}
	code := b.String()
	if len(code) != CodeLen {
		return "", false
	}
	return code[:4] + "-" + code[4:8] + "-" + code[8:], true
}

type Session struct {
	TicketID int64  `json:"ticket_id"`
	Subject  string `json:"subject"`
	// The customer's own subscription link, so they need not find and paste
	// it. Empty when the panel could not be asked.
	SubscriptionURL string `json:"subscription_url"`
	ExpiresAt       int64  `json:"expires_at"`
}

// Error is what the site answered with, in its own words.
type Error struct {
	Status  int
	Code    string
	Message string
}

func (e *Error) Error() string {
	if e.Message != "" {
		return e.Message
	}
	return fmt.Sprintf("сайт ответил HTTP %d", e.Status)
}

type Client struct {
	site string
	http *http.Client
}

func New(site string) *Client {
	return &Client{
		site: strings.TrimRight(site, "/"),
		// Straight to the site, past any proxy in the environment: the
		// same route the checks took.
		http: &http.Client{Transport: &http.Transport{Proxy: nil}, Timeout: 2 * time.Minute},
	}
}

// Open checks the code and learns which ticket it is for, before anything
// is checked -- a mistyped code is better found now than after the run.
func (c *Client) Open(ctx context.Context, code string) (*Session, error) {
	body, _ := json.Marshal(map[string]string{"code": code})
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.site+"/api/support/diagnostics/session", bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	var session Session
	if err := c.do(req, &session); err != nil {
		return nil, err
	}
	return &session, nil
}

// Upload attaches the report file to the ticket, with a one-line summary
// as the message text.
func (c *Client) Upload(ctx context.Context, code, summary, path string) error {
	data, err := os.ReadFile(path)
	if err != nil {
		return err
	}
	var body bytes.Buffer
	form := multipart.NewWriter(&body)
	_ = form.WriteField("code", code)
	_ = form.WriteField("summary", summary)
	part, err := form.CreateFormFile("file", filepath.Base(path))
	if err != nil {
		return err
	}
	if _, err := part.Write(data); err != nil {
		return err
	}
	if err := form.Close(); err != nil {
		return err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.site+"/api/support/diagnostics/report", &body)
	if err != nil {
		return err
	}
	req.Header.Set("Content-Type", form.FormDataContentType())
	return c.do(req, nil)
}

func (c *Client) do(req *http.Request, into any) error {
	req.Header.Set("Accept", "application/json")
	resp, err := c.http.Do(req)
	if err != nil {
		return err
	}
	defer resp.Body.Close()
	data, err := io.ReadAll(io.LimitReader(resp.Body, 1<<20))
	if err != nil {
		return err
	}
	if resp.StatusCode/100 != 2 {
		var problem struct {
			Error   string `json:"error"`
			Message string `json:"message"`
		}
		_ = json.Unmarshal(data, &problem)
		return &Error{Status: resp.StatusCode, Code: problem.Error, Message: problem.Message}
	}
	if into == nil {
		return nil
	}
	if err := json.Unmarshal(data, into); err != nil {
		return errors.New("сайт ответил не тем, что ждали: " + err.Error())
	}
	return nil
}
