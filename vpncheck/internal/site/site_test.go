package site

import (
	"context"
	"encoding/json"
	"errors"
	"io"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
)

const link = "https://sub.example.net/Ab3dE6gH9jK2mN4p"

func TestStatusAndSend(t *testing.T) {
	var sent struct{ link, summary, note, name, body string }
	server := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/api/vpncheck/status":
			var body map[string]string
			_ = json.NewDecoder(r.Body).Decode(&body)
			if body["link"] != link {
				w.WriteHeader(http.StatusNotFound)
				_, _ = io.WriteString(w, `{"error":"subscription_not_found","message":"Подписка не найдена."}`)
				return
			}
			_, _ = io.WriteString(w, `{"state":"active","expires_at":1800000000,"days_left":12,"tier":"paid","renew_url":"https://example.net/app/plans"}`)
		case "/api/vpncheck/report":
			file, header, err := r.FormFile("file")
			if err != nil {
				t.Error(err)
				return
			}
			data, _ := io.ReadAll(file)
			sent.link, sent.summary, sent.note = r.FormValue("link"), r.FormValue("summary"), r.FormValue("note")
			sent.name, sent.body = header.Filename, string(data)
			w.WriteHeader(http.StatusCreated)
			_, _ = io.WriteString(w, `{"ticket_id":12,"created":true}`)
		}
	}))
	defer server.Close()
	client := New(server.URL + "/")

	status, err := client.Status(context.Background(), link)
	if err != nil || status.State != "active" || status.DaysLeft != 12 || *status.ExpiresAt != 1800000000 ||
		status.RenewURL != "https://example.net/app/plans" {
		t.Fatalf("%+v %v", status, err)
	}
	_, err = client.Status(context.Background(), "https://sub.example.net/other")
	var siteErr *Error
	if !errors.As(err, &siteErr) || siteErr.Status != http.StatusNotFound || siteErr.Code != "subscription_not_found" ||
		err.Error() != "Подписка не найдена." {
		t.Fatalf("%v", err)
	}

	path := filepath.Join(t.TempDir(), "report.txt")
	if err := os.WriteFile(path, []byte("отчёт"), 0o644); err != nil {
		t.Fatal(err)
	}
	result, err := client.Send(context.Background(), link, "работает 1 из 1", "  YouTube не грузит ", path)
	if err != nil || result.TicketID != 12 || !result.Created {
		t.Fatalf("%+v %v", result, err)
	}
	if sent.link != link || sent.summary != "работает 1 из 1" || sent.note != "YouTube не грузит" ||
		sent.name != "report.txt" || sent.body != "отчёт" {
		t.Fatalf("%+v", sent)
	}
}
