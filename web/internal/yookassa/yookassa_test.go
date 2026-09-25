package yookassa

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"testing"
)

// The metadata below is a contract with the Python webhook: it reads
// telegram_id, days_to_extend, is_gift and lte_gb back from a *verified* fetch
// and credits accordingly. These tests pin the field names and value shapes
// against user_bot/payments/yookassa_client.py -- a rename on either side is a
// payment that gets taken and never credited.

func capture(t *testing.T, req Request) (map[string]any, *http.Request) {
	t.Helper()

	var body map[string]any
	var seen *http.Request

	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		seen = r.Clone(r.Context())
		raw, _ := io.ReadAll(r.Body)
		if err := json.Unmarshal(raw, &body); err != nil {
			t.Errorf("request body was not JSON: %v", err)
		}
		w.Header().Set("Content-Type", "application/json")
		_, _ = w.Write([]byte(`{"id":"pay-1","status":"pending",
			"confirmation":{"confirmation_url":"https://yoo/confirm"}}`))
	}))
	t.Cleanup(server.Close)

	client := New("shop", "secret")
	client.SetEndpoint(server.URL)
	if _, err := client.CreatePayment(context.Background(), req); err != nil {
		t.Fatalf("CreatePayment: %v", err)
	}
	return body, seen
}

func metadata(t *testing.T, body map[string]any) map[string]any {
	t.Helper()
	meta, ok := body["metadata"].(map[string]any)
	if !ok {
		t.Fatalf("no metadata in %v", body)
	}
	return meta
}

func TestSubscriptionMetadataMatchesTheWebhookContract(t *testing.T) {
	body, _ := capture(t, Request{
		AmountRubles: 249, Description: "Подписка", TelegramID: 555, DaysToExtend: 90,
	})
	meta := metadata(t, body)

	// Strings, not numbers: the Python side reads them with int(...) and a
	// JSON number would arrive as a float and fail on a value like 90.0.
	for key, want := range map[string]any{
		"telegram_id":    "555",
		"days_to_extend": "90",
		"is_gift":        "false",
		"lte_gb":         "0",
	} {
		if got := meta[key]; got != want {
			t.Errorf("metadata[%q] = %v, want %v", key, got, want)
		}
	}
}

func TestTrafficPurchaseCarriesGigabytesAndNoDays(t *testing.T) {
	// The webhook branches on lte_gb: a traffic purchase must credit
	// gigabytes and leave the subscription date untouched.
	body, _ := capture(t, Request{
		AmountRubles: 119, Description: "Трафик", TelegramID: 555, DaysToExtend: 0, LTEGigabytes: 10,
	})
	meta := metadata(t, body)

	if meta["lte_gb"] != "10" {
		t.Errorf("lte_gb = %v, want \"10\"", meta["lte_gb"])
	}
	if meta["days_to_extend"] != "0" {
		t.Errorf("days_to_extend = %v, want \"0\"", meta["days_to_extend"])
	}
}

func TestGiftIsFlaggedAsSuch(t *testing.T) {
	body, _ := capture(t, Request{AmountRubles: 89, TelegramID: 555, DaysToExtend: 30, IsGift: true})

	if got := metadata(t, body)["is_gift"]; got != "true" {
		t.Errorf("is_gift = %v, want \"true\"", got)
	}
}

func TestAmountIsSentWithTwoDecimals(t *testing.T) {
	// YooKassa rejects a bare integer amount.
	body, _ := capture(t, Request{AmountRubles: 89, TelegramID: 1})
	amount := body["amount"].(map[string]any)

	if amount["value"] != "89.00" {
		t.Errorf("amount = %v, want \"89.00\"", amount["value"])
	}
	if amount["currency"] != "RUB" {
		t.Errorf("currency = %v, want RUB", amount["currency"])
	}
}

func TestReceiptFallsBackToAPlaceholderAddress(t *testing.T) {
	// A fiscal receipt needs an address; a user without one on file must not
	// block the purchase.
	body, _ := capture(t, Request{AmountRubles: 89, TelegramID: 1})
	receipt := body["receipt"].(map[string]any)
	customer := receipt["customer"].(map[string]any)

	if customer["email"] != receiptEmail {
		t.Errorf("receipt email = %v, want %v", customer["email"], receiptEmail)
	}
}

func TestTheUsersOwnAddressIsUsedWhenKnown(t *testing.T) {
	body, _ := capture(t, Request{AmountRubles: 89, TelegramID: 1, Email: "bob@example.com"})
	customer := body["receipt"].(map[string]any)["customer"].(map[string]any)

	if customer["email"] != "bob@example.com" {
		t.Errorf("receipt email = %v", customer["email"])
	}
}

func TestEveryRequestCarriesAnIdempotenceKey(t *testing.T) {
	// Without it a retried request charges the customer a second time.
	_, seen := capture(t, Request{AmountRubles: 89, TelegramID: 1})

	if seen.Header.Get("Idempotence-Key") == "" {
		t.Error("no Idempotence-Key header")
	}
}

func TestRequestsAreAuthenticated(t *testing.T) {
	_, seen := capture(t, Request{AmountRubles: 89, TelegramID: 1})

	shop, secret, ok := seen.BasicAuth()
	if !ok || shop != "shop" || secret != "secret" {
		t.Errorf("basic auth = (%q, %q, %v)", shop, secret, ok)
	}
}

func TestMissingCredentialsFailBeforeAnyRequest(t *testing.T) {
	if _, err := New("", "").CreatePayment(context.Background(), Request{}); !errors.Is(err, ErrNotConfigured) {
		t.Errorf("expected ErrNotConfigured, got %v", err)
	}
}

func TestAnErrorResponseIsNotMistakenForAPayment(t *testing.T) {
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		w.WriteHeader(http.StatusBadRequest)
		_, _ = w.Write([]byte(`{"type":"error","description":"bad amount"}`))
	}))
	defer server.Close()

	client := New("shop", "secret")
	client.SetEndpoint(server.URL)

	if _, err := client.CreatePayment(context.Background(), Request{AmountRubles: 1}); err == nil {
		t.Fatal("expected an error")
	}
}

func TestAResponseWithoutAPaymentIDIsAnError(t *testing.T) {
	// Returning a payment with an empty ID would give the caller something to
	// record and poll that can never resolve.
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		_, _ = w.Write([]byte(`{"status":"pending"}`))
	}))
	defer server.Close()

	client := New("shop", "secret")
	client.SetEndpoint(server.URL)

	if _, err := client.CreatePayment(context.Background(), Request{AmountRubles: 1}); err == nil {
		t.Fatal("expected an error")
	}
}
