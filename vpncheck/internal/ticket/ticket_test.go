package ticket

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

func TestNormalizeCode(t *testing.T) {
	for input, want := range map[string]string{
		"ABCD-EFGH-JKLM":   "ABCD-EFGH-JKLM",
		" abcd efgh jklm ": "ABCD-EFGH-JKLM",
		"abcdefghjklm":     "ABCD-EFGH-JKLM",
		"2345-6789-ABCD":   "2345-6789-ABCD",
	} {
		if got, ok := NormalizeCode(input); !ok || got != want {
			t.Errorf("%q: %q %v", input, got, ok)
		}
	}
	for _, input := range []string{"", "ABCD-EFGH", "ABCD-EFGH-JKL0", "ABCD-EFGH-JKLI", "https://example.com/sub/abc"} {
		if _, ok := NormalizeCode(input); ok {
			t.Errorf("%q accepted", input)
		}
	}
}

func TestOpenAndUpload(t *testing.T) {
	var uploaded struct{ code, summary, name, body string }
	site := httptest.NewServer(http.HandlerFunc(func(w http.ResponseWriter, r *http.Request) {
		switch r.URL.Path {
		case "/api/support/diagnostics/session":
			var body map[string]string
			_ = json.NewDecoder(r.Body).Decode(&body)
			if body["code"] != "ABCD-EFGH-JKLM" {
				w.WriteHeader(http.StatusNotFound)
				_, _ = io.WriteString(w, `{"error":"code_invalid","message":"Код не подошёл."}`)
				return
			}
			_, _ = io.WriteString(w, `{"ticket_id":12,"subject":"Не работает","subscription_url":"https://sub.example.net/x","expires_at":1}`)
		case "/api/support/diagnostics/report":
			file, header, err := r.FormFile("file")
			if err != nil {
				t.Error(err)
				return
			}
			data, _ := io.ReadAll(file)
			uploaded.code, uploaded.summary = r.FormValue("code"), r.FormValue("summary")
			uploaded.name, uploaded.body = header.Filename, string(data)
			w.WriteHeader(http.StatusCreated)
			_, _ = io.WriteString(w, `{"ok":true}`)
		}
	}))
	defer site.Close()
	client := New(site.URL + "/")

	session, err := client.Open(context.Background(), "ABCD-EFGH-JKLM")
	if err != nil || session.TicketID != 12 || session.SubscriptionURL != "https://sub.example.net/x" {
		t.Fatalf("%+v %v", session, err)
	}
	_, err = client.Open(context.Background(), "ZZZZ-ZZZZ-ZZZZ")
	var siteErr *Error
	if !errors.As(err, &siteErr) || siteErr.Status != http.StatusNotFound || err.Error() != "Код не подошёл." {
		t.Fatalf("%v", err)
	}

	path := filepath.Join(t.TempDir(), "report.txt")
	if err := os.WriteFile(path, []byte("отчёт"), 0o644); err != nil {
		t.Fatal(err)
	}
	if err := client.Upload(context.Background(), "ABCD-EFGH-JKLM", "работает 1 из 1", path); err != nil {
		t.Fatal(err)
	}
	if uploaded.code != "ABCD-EFGH-JKLM" || uploaded.summary != "работает 1 из 1" || uploaded.name != "report.txt" || uploaded.body != "отчёт" {
		t.Fatalf("%+v", uploaded)
	}
}
