// Package site asks the website about a subscription and sends it reports,
// with nothing but the customer's subscription link.
//
// The link is the whole authorisation: whoever holds it already uses that
// customer's VPN, so it may as well say whose subscription and whose ticket.
// vpncheck holds no account and no session, and the site answers no more
// than the customer's own app already shows -- and takes a report into their
// own ticket. Sending is the customer's decision: nothing here runs before
// they press the button or pass -send.
package site

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

// Status is the subscription as our records have it. The panel's own date
// says nothing about payment: with the free tier on, every account in it
// runs ten years ahead.
type Status struct {
	// active: paid or trial time is running. free: it is not, and the free
	// tier keeps some servers open. expired: it is not, and nothing is open.
	// none: there never was any.
	State     string `json:"state"`
	ExpiresAt *int64 `json:"expires_at"`
	DaysLeft  int    `json:"days_left"`
	Tier      string `json:"tier"`
	// Where to pay.
	RenewURL string `json:"renew_url"`
}

// Sent is where a report went.
type Sent struct {
	TicketID int64 `json:"ticket_id"`
	// A ticket was opened for it: the customer had none open.
	Created bool `json:"created"`
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

// Status asks what the subscription behind link is.
func (c *Client) Status(ctx context.Context, link string) (*Status, error) {
	body, _ := json.Marshal(map[string]string{"link": link})
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.site+"/api/vpncheck/status", bytes.NewReader(body))
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", "application/json")
	var status Status
	if err := c.do(req, &status); err != nil {
		return nil, err
	}
	return &status, nil
}

// Send puts the report file into the customer's open ticket, or opens one,
// with a one-line summary and whatever the customer wrote as the message.
func (c *Client) Send(ctx context.Context, link, summary, note, path string) (*Sent, error) {
	data, err := os.ReadFile(path)
	if err != nil {
		return nil, err
	}
	var body bytes.Buffer
	form := multipart.NewWriter(&body)
	_ = form.WriteField("link", link)
	_ = form.WriteField("summary", summary)
	if note = strings.TrimSpace(note); note != "" {
		_ = form.WriteField("note", note)
	}
	part, err := form.CreateFormFile("file", filepath.Base(path))
	if err != nil {
		return nil, err
	}
	if _, err := part.Write(data); err != nil {
		return nil, err
	}
	if err := form.Close(); err != nil {
		return nil, err
	}
	req, err := http.NewRequestWithContext(ctx, http.MethodPost, c.site+"/api/vpncheck/report", &body)
	if err != nil {
		return nil, err
	}
	req.Header.Set("Content-Type", form.FormDataContentType())
	var sent Sent
	if err := c.do(req, &sent); err != nil {
		return nil, err
	}
	return &sent, nil
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
	if err := json.Unmarshal(data, into); err != nil {
		return errors.New("сайт ответил не тем, что ждали: " + err.Error())
	}
	return nil
}
