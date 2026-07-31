// Package yookassa creates payments.
//
// Creating is all it does. Confirming a payment -- deciding it succeeded and
// crediting the user -- happens exclusively in the Python webhook handler,
// which re-fetches the payment server-to-server because YooKassa's callback
// carries no signature of its own. Two services doing that would race to
// credit the same payment, so this one does not have the capability at all.
package yookassa

import (
	"bytes"
	"context"
	"crypto/rand"
	"encoding/hex"
	"encoding/json"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strconv"
	"time"
)

const apiURL = "https://api.yookassa.ru/v3/payments"

// receiptEmail is the address put on the fiscal receipt when we have nothing
// better. Matches what the bot sends.
const receiptEmail = "no-reply@nitravpn.com"

type Client struct {
	shopID    string
	secretKey string
	http      *http.Client
	// baseOverride redirects requests at a test server. Empty in production.
	baseOverride string
}

// SetEndpoint points the client at a different URL, for tests.
func (c *Client) SetEndpoint(url string) { c.baseOverride = url }

func New(shopID, secretKey string) *Client {
	return &Client{
		shopID:    shopID,
		secretKey: secretKey,
		http:      &http.Client{Timeout: 15 * time.Second},
	}
}

// Request describes a payment to create.
//
// Metadata is the contract with the Python webhook: it reads `telegram_id`,
// `days_to_extend`, `is_gift` and `lte_gb` back from a *verified* fetch and
// credits accordingly. The field names and value shapes here must match
// user_bot/payments/yookassa_client.py exactly, which is what
// yookassa_test.go pins.
type Request struct {
	AmountRubles int
	Description  string
	ReturnURL    string
	TelegramID   int64
	DaysToExtend int
	IsGift       bool
	LTEGigabytes int
	Email        string
}

type Payment struct {
	ID         string
	Status     string
	ConfirmURL string
}

var ErrNotConfigured = errors.New("yookassa: shop id or secret key is missing")

func (c *Client) CreatePayment(ctx context.Context, req Request) (*Payment, error) {
	if c.shopID == "" || c.secretKey == "" {
		return nil, ErrNotConfigured
	}

	amount := strconv.Itoa(req.AmountRubles) + ".00"
	email := req.Email
	if email == "" {
		email = receiptEmail
	}

	body := map[string]any{
		"amount":       map[string]string{"value": amount, "currency": "RUB"},
		"confirmation": map[string]string{"type": "redirect", "return_url": req.ReturnURL},
		"capture":      true,
		"description":  req.Description,
		"metadata": map[string]string{
			"telegram_id":    strconv.FormatInt(req.TelegramID, 10),
			"days_to_extend": strconv.Itoa(req.DaysToExtend),
			"is_gift":        boolString(req.IsGift),
			"lte_gb":         strconv.Itoa(req.LTEGigabytes),
			// Marks where the payment came from. The webhook ignores it; it
			// exists so a support question about a charge can be answered
			// without guessing.
			"source": "web",
		},
		"receipt": map[string]any{
			"customer": map[string]string{"email": email},
			"items": []map[string]any{{
				"description":     req.Description,
				"quantity":        "1.00",
				"amount":          map[string]string{"value": amount, "currency": "RUB"},
				"vat_code":        1,
				"payment_mode":    "full_payment",
				"payment_subject": "service",
			}},
		},
	}

	encoded, err := json.Marshal(body)
	if err != nil {
		return nil, err
	}
	httpReq, err := http.NewRequestWithContext(ctx, http.MethodPost, c.endpoint(), bytes.NewReader(encoded))
	if err != nil {
		return nil, err
	}
	httpReq.SetBasicAuth(c.shopID, c.secretKey)
	httpReq.Header.Set("Content-Type", "application/json")
	// YooKassa deduplicates on this: a retried request with the same key
	// returns the original payment instead of charging twice.
	idempotenceKey, err := randomHex(16)
	if err != nil {
		return nil, err
	}
	httpReq.Header.Set("Idempotence-Key", idempotenceKey)

	resp, err := c.http.Do(httpReq)
	if err != nil {
		return nil, fmt.Errorf("yookassa: create payment: %w", err)
	}
	defer resp.Body.Close()

	if resp.StatusCode >= 400 {
		snippet, _ := io.ReadAll(io.LimitReader(resp.Body, 512))
		return nil, fmt.Errorf("yookassa: create payment returned %d: %s", resp.StatusCode, snippet)
	}

	var parsed struct {
		ID           string `json:"id"`
		Status       string `json:"status"`
		Confirmation struct {
			ConfirmationURL string `json:"confirmation_url"`
		} `json:"confirmation"`
	}
	if err := json.NewDecoder(resp.Body).Decode(&parsed); err != nil {
		return nil, fmt.Errorf("yookassa: decode payment: %w", err)
	}
	if parsed.ID == "" {
		return nil, errors.New("yookassa: response carried no payment id")
	}
	return &Payment{ID: parsed.ID, Status: parsed.Status, ConfirmURL: parsed.Confirmation.ConfirmationURL}, nil
}

// endpoint is overridable in tests; production always uses YooKassa's API.
func (c *Client) endpoint() string {
	if c.baseOverride != "" {
		return c.baseOverride
	}
	return apiURL
}

func boolString(v bool) string {
	if v {
		return "true"
	}
	return "false"
}

func randomHex(n int) (string, error) {
	buf := make([]byte, n)
	if _, err := rand.Read(buf); err != nil {
		return "", err
	}
	return hex.EncodeToString(buf), nil
}
