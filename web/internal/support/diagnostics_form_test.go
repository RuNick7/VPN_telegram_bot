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
	r := httptest.NewRequest(http.MethodPost, "/api/support/diagnostics/report", &body)
	r.Header.Set("Content-Type", form.FormDataContentType())
	return r
}

func TestReadDiagnosticsReport(t *testing.T) {
	report, err := ReadDiagnosticsReport(reportRequest(t,
		map[string]string{"code": "ABCD-EFGH-JKLM", "summary": "работает 1 из 2\nсерверов"},
		[]byte("Проверка серверов vpncheck\n\tлог\r\n")))
	if err != nil {
		t.Fatal(err)
	}
	if report.Code != "ABCD-EFGH-JKLM" || report.Summary != "работает 1 из 2 серверов" {
		t.Errorf("%+v", report)
	}
	// Stored under one fixed name, whatever the program called it.
	if report.File.Name != DiagnosticsFileName || report.File.ContentType != "text/plain" {
		t.Errorf("%+v", report.File)
	}
}

func TestReadDiagnosticsReportRefuses(t *testing.T) {
	for name, tc := range map[string]struct {
		fields map[string]string
		file   []byte
		code   string
	}{
		"binary file":   {map[string]string{"code": "ABCD-EFGH-JKLM"}, []byte("\x89PNG\r\n\x1a\nxxxx"), "unsupported_file"},
		"no file":       {map[string]string{"code": "ABCD-EFGH-JKLM"}, nil, "bad_request"},
		"no code":       {map[string]string{"summary": "x"}, []byte("text"), "bad_request"},
		"unknown field": {map[string]string{"code": "ABCD-EFGH-JKLM", "ticket": "1"}, []byte("text"), "bad_request"},
		"too large":     {map[string]string{"code": "ABCD-EFGH-JKLM"}, []byte(strings.Repeat("a", MaxDocumentBytes+1)), "file_too_large"},
	} {
		t.Run(name, func(t *testing.T) {
			_, err := ReadDiagnosticsReport(reportRequest(t, tc.fields, tc.file))
			var problem *Problem
			if !errors.As(err, &problem) || problem.Code != tc.code {
				t.Fatalf("%v, want %s", err, tc.code)
			}
		})
	}
}
