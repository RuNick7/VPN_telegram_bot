package support

import (
	"bytes"
	"errors"
	"mime/multipart"
	"net/http"
	"net/http/httptest"
	"strings"
	"testing"
)

func TestSubscriptionID(t *testing.T) {
	for link, want := range map[string]string{
		"https://sub.kairavpn.pro/Ab3dE6gH9jK2mN4p":             "Ab3dE6gH9jK2mN4p",
		"  https://sub.kairavpn.pro/Ab3dE6gH9jK2mN4p/ \n":       "Ab3dE6gH9jK2mN4p",
		"https://sub.example.com/api/sub/Ab3d-E6_g?x=1#профиль": "Ab3d-E6_g",
		"http://127.0.0.1:8080/Ab3dE6gH":                        "Ab3dE6gH",
		"https://sub.kairavpn.pro/":                             "",
		"https://sub.kairavpn.pro/abc":                          "",
		"https://sub.kairavpn.pro/Ab3dE6gH9jK2mN4p%2F..":        "",
		"vless://uuid@host:443":                                 "",
		"happ://add/https://sub.kairavpn.pro/Ab3dE6gH9jK2mN4p":  "",
		"sub.kairavpn.pro/Ab3dE6gH9jK2mN4p":                     "",
	} {
		got, ok := SubscriptionID(link)
		if got != want || ok != (want != "") {
			t.Errorf("%q: %q %v, want %q", link, got, ok, want)
		}
	}
}

const sampleReport = "Проверка серверов vpncheck 1.0 (Xray 25.1)\nИтог: работает 1 из 2\n"

func reportRequest(t *testing.T, fields map[string]string, file []byte) *http.Request {
	t.Helper()
	var body bytes.Buffer
	form := multipart.NewWriter(&body)
	for name, value := range fields {
		_ = form.WriteField(name, value)
	}
	if file != nil {
		part, _ := form.CreateFormFile("file", "../report.exe")
		_, _ = part.Write(file)
	}
	_ = form.Close()
	r := httptest.NewRequest(http.MethodPost, "/api/vpncheck/report", &body)
	r.Header.Set("Content-Type", form.FormDataContentType())
	return r
}

func TestReadVpncheckReport(t *testing.T) {
	report, err := ReadVpncheckReport(reportRequest(t,
		map[string]string{
			"link":    "https://sub.kairavpn.pro/Ab3dE6gH9jK2mN4p",
			"summary": "работает 1 из 2\nсерверов",
			"note":    "  Не открывается YouTube\r\nс вечера\x00 ",
		},
		[]byte(sampleReport+"\tлог\r\n")))
	if err != nil {
		t.Fatal(err)
	}
	if report.Link != "https://sub.kairavpn.pro/Ab3dE6gH9jK2mN4p" || report.Summary != "работает 1 из 2 серверов" ||
		report.Note != "Не открывается YouTube\nс вечера" {
		t.Errorf("%+v", report)
	}
	// Stored under one fixed name, whatever the program called it.
	if report.File.Name != ReportFileName || report.File.ContentType != "text/plain" {
		t.Errorf("%+v", report.File)
	}
	if got := ReportMessage(report); got != "Не открывается YouTube\nс вечера\n\n🩺 работает 1 из 2 серверов" {
		t.Errorf("message %q", got)
	}
	report.Note, report.Summary = "", ""
	if got := ReportMessage(report); got != "🩺 Отчёт проверки серверов (vpncheck)" {
		t.Errorf("message %q", got)
	}
}

func TestReadVpncheckReportRefuses(t *testing.T) {
	link := "https://sub.kairavpn.pro/Ab3dE6gH9jK2mN4p"
	for name, tc := range map[string]struct {
		fields map[string]string
		file   []byte
		code   string
	}{
		"binary file":   {map[string]string{"link": link}, []byte("\x89PNG\r\n\x1a\nxxxx"), "not_a_report"},
		"other text":    {map[string]string{"link": link}, []byte("hello"), "not_a_report"},
		"no file":       {map[string]string{"link": link}, nil, "bad_request"},
		"no link":       {map[string]string{"summary": "x"}, []byte(sampleReport), "bad_request"},
		"unknown field": {map[string]string{"link": link, "ticket": "1"}, []byte(sampleReport), "bad_request"},
		"too large":     {map[string]string{"link": link}, []byte(sampleReport + strings.Repeat("a", MaxDocumentBytes)), "file_too_large"},
	} {
		t.Run(name, func(t *testing.T) {
			_, err := ReadVpncheckReport(reportRequest(t, tc.fields, tc.file))
			var problem *Problem
			if !errors.As(err, &problem) || problem.Code != tc.code {
				t.Fatalf("%v, want %s", err, tc.code)
			}
		})
	}
}

func TestScrubReport(t *testing.T) {
	data := []byte("Подписка https://sub.kairavpn.pro/Ab3dE6gH9jK2mN4p\nи ещё Ab3dE6gH9jK2mN4p, но не Ab3d\n")
	got := string(ScrubReport(data, "Ab3dE6gH9jK2mN4p"))
	if strings.Contains(got, "Ab3dE6gH9jK2mN4p") || !strings.Contains(got, "https://sub.kairavpn.pro/[скрыто:подписка]") ||
		!strings.Contains(got, "но не Ab3d") {
		t.Errorf("%q", got)
	}
}
