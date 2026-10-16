package support

import (
	"crypto/sha256"
	"errors"
	"fmt"
	"io"
	"net/http"
	"strings"
	"unicode/utf8"
)

// Codes for sending a server-check report into a ticket.
//
// user_bot hands one to a customer who agreed to the check; the vpncheck
// program brings it back with the report. The rules are the bot's, in
// shared/tgvpn_shared/support_diagnostics.py, and the test vectors on both
// sides keep the hash the same.

// DiagnosticsAlphabet leaves out 0/O and 1/I: the code is read off a phone.
const DiagnosticsAlphabet = "23456789ABCDEFGHJKLMNPQRSTUVWXYZ"

// DiagnosticsCodeLen is 60 bits of code, which with the endpoints' rate limit
// and a lifetime of days is far out of reach of guessing.
const DiagnosticsCodeLen = 12

// MaxDiagnosticsSummaryRunes bounds the one line vpncheck sends with a report
// as the message text.
const MaxDiagnosticsSummaryRunes = 500

// NormalizeDiagnosticsCode reads a code as typed -- any case, with dashes or
// spaces -- into its canonical form, or reports that it is not one.
func NormalizeDiagnosticsCode(text string) (string, bool) {
	var b strings.Builder
	for _, r := range strings.ToUpper(text) {
		switch {
		case r == '-' || r == ' ':
		case strings.ContainsRune(DiagnosticsAlphabet, r):
			b.WriteRune(r)
		default:
			return "", false
		}
	}
	if b.Len() != DiagnosticsCodeLen {
		return "", false
	}
	return b.String(), true
}

// HashDiagnosticsCode is what the database keeps in place of the code.
func HashDiagnosticsCode(text string) ([]byte, bool) {
	code, ok := NormalizeDiagnosticsCode(text)
	if !ok {
		return nil, false
	}
	sum := sha256.Sum256([]byte(code))
	return sum[:], true
}

// DiagnosticsReport is what vpncheck sends: the code, a one-line summary for
// the message text, and the report file.
type DiagnosticsReport struct {
	Code    string
	Summary string
	File    File
}

// DiagnosticsFileName is what the report is stored as, whatever the program
// called it: one name the operators learn to recognise.
const DiagnosticsFileName = "vpncheck-report.txt"

// ReadDiagnosticsReport reads vpncheck's multipart upload with the same care
// as a customer's message: streamed, each part under its own limit, the file
// judged by its content. A report is text, and only text is taken.
func ReadDiagnosticsReport(r *http.Request) (*DiagnosticsReport, error) {
	reader, err := r.MultipartReader()
	if err != nil {
		return nil, problem(http.StatusBadRequest, "bad_request", "Некорректный запрос.")
	}
	var report DiagnosticsReport
	seen := map[string]bool{}
	for {
		part, err := reader.NextPart()
		if errors.Is(err, io.EOF) {
			break
		}
		if err != nil {
			return nil, readProblem(err)
		}
		name := part.FormName()
		if seen[name] {
			return nil, problem(http.StatusBadRequest, "bad_request", "Некорректный запрос.")
		}
		seen[name] = true
		switch name {
		case "code":
			if report.Code, err = readText(part, 64); err != nil {
				return nil, err
			}
		case "summary":
			if report.Summary, err = readText(part, MaxDiagnosticsSummaryRunes*utf8.UTFMax); err != nil {
				return nil, err
			}
		case "file":
			data, err := io.ReadAll(io.LimitReader(part, MaxDocumentBytes+1))
			if err != nil {
				return nil, readProblem(err)
			}
			if int64(len(data)) > MaxDocumentBytes {
				return nil, problem(http.StatusRequestEntityTooLarge, "file_too_large",
					fmt.Sprintf("Отчёт больше %d МБ.", MaxDocumentBytes>>20))
			}
			if len(data) == 0 || Detect(data) != "text/plain" {
				return nil, problem(http.StatusUnsupportedMediaType, "unsupported_file", "Отчёт должен быть текстовым файлом.")
			}
			report.File = File{Name: DiagnosticsFileName, ContentType: "text/plain", Data: data}
		default:
			return nil, problem(http.StatusBadRequest, "bad_request", "Некорректный запрос.")
		}
	}
	if !seen["code"] || !seen["file"] {
		return nil, problem(http.StatusBadRequest, "bad_request", "Некорректный запрос.")
	}
	report.Summary = normalizeSubject(report.Summary)
	if utf8.RuneCountInString(report.Summary) > MaxDiagnosticsSummaryRunes {
		report.Summary = string([]rune(report.Summary)[:MaxDiagnosticsSummaryRunes])
	}
	return &report, nil
}
