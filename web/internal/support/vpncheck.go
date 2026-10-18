package support

import (
	"bytes"
	"errors"
	"fmt"
	"io"
	"net/http"
	"net/url"
	"regexp"
	"strings"
	"unicode/utf8"
)

// Server-check reports from the vpncheck program.
//
// The program runs on the customer's computer with nothing but their
// subscription link, and the link is the whole authorisation: whoever holds
// it already uses that customer's VPN, so it may as well tell us whose ticket
// a report belongs in. Pressing «Отправить в поддержку» is the consent.

// subscriptionID is what a panel names a subscription by in its links: the
// last path segment, letters, digits, '-' and '_'.
var subscriptionID = regexp.MustCompile(`^[A-Za-z0-9_-]{6,64}$`)

// SubscriptionID takes the subscription's identifier out of a link as the
// customer has it. Only the identifier is used: the site never fetches the
// link, so a link to anywhere else cannot make it fetch anything.
func SubscriptionID(link string) (string, bool) {
	parsed, err := url.Parse(strings.TrimSpace(link))
	if err != nil || (parsed.Scheme != "https" && parsed.Scheme != "http") || parsed.Host == "" {
		return "", false
	}
	path := strings.TrimRight(parsed.Path, "/")
	id := path[strings.LastIndex(path, "/")+1:]
	if !subscriptionID.MatchString(id) {
		return "", false
	}
	return id, true
}

// ReportHeader is how every vpncheck report begins (internal/report.Summary
// in vpncheck). Anything else is not a report, whatever it is called.
const ReportHeader = "Проверка серверов vpncheck "

const (
	// MaxReportSummaryRunes bounds the one line vpncheck sends with a report
	// for the message text.
	MaxReportSummaryRunes = 500
	// MaxReportNoteRunes bounds what the customer typed into «Что не
	// работает?».
	MaxReportNoteRunes = 1000
	// ReportsPerDay is how many reports one customer may send in a rolling
	// day. A check takes minutes; more than this is a loop, not a problem.
	ReportsPerDay = 5
	// ReportSubject names the ticket a report opens when none is open.
	ReportSubject = "Проверка серверов"
	// ReportFileName is what a report is stored as, whatever the program
	// called it: one name the operators learn to recognise.
	ReportFileName = "vpncheck-report.txt"
)

// VpncheckReport is what vpncheck sends: the link, a one-line summary, the
// customer's own words if any, and the report file.
type VpncheckReport struct {
	Link    string
	Summary string
	Note    string
	File    File
}

// ReadVpncheckReport reads vpncheck's multipart upload with the same care as
// a customer's message: streamed, each part under its own limit, the file
// judged by its content. Only a vpncheck report is taken.
func ReadVpncheckReport(r *http.Request) (*VpncheckReport, error) {
	reader, err := r.MultipartReader()
	if err != nil {
		return nil, problem(http.StatusBadRequest, "bad_request", "Некорректный запрос.")
	}
	var report VpncheckReport
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
		case "link":
			if report.Link, err = readText(part, 2048); err != nil {
				return nil, err
			}
		case "summary":
			if report.Summary, err = readText(part, MaxReportSummaryRunes*utf8.UTFMax); err != nil {
				return nil, err
			}
		case "note":
			if report.Note, err = readText(part, MaxReportNoteRunes*utf8.UTFMax); err != nil {
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
			if Detect(data) != "text/plain" || !bytes.HasPrefix(data, []byte(ReportHeader)) {
				return nil, problem(http.StatusUnsupportedMediaType, "not_a_report", "Это не отчёт программы проверки.")
			}
			report.File = File{Name: ReportFileName, ContentType: "text/plain", Data: data}
		default:
			return nil, problem(http.StatusBadRequest, "bad_request", "Некорректный запрос.")
		}
	}
	if !seen["link"] || !seen["file"] {
		return nil, problem(http.StatusBadRequest, "bad_request", "Некорректный запрос.")
	}
	report.Summary = truncateRunes(normalizeSubject(report.Summary), MaxReportSummaryRunes)
	report.Note = truncateRunes(normalizeBody(report.Note), MaxReportNoteRunes)
	return &report, nil
}

func truncateRunes(s string, n int) string {
	if utf8.RuneCountInString(s) <= n {
		return s
	}
	return string([]rune(s)[:n])
}

// ScrubReport cuts the subscription out of a report once more. vpncheck
// already does, but a report goes into a ticket the operators forward, and
// an old or broken build must not be able to put a working link there.
// Every form of the link contains its identifier, so that is what goes.
func ScrubReport(data []byte, id string) []byte {
	if id == "" {
		return data
	}
	return bytes.ReplaceAll(data, []byte(id), []byte("[скрыто:подписка]"))
}

// ReportMessage is the text of the customer's message a report arrives in:
// their own words first, if they wrote any, then the summary.
func ReportMessage(report *VpncheckReport) string {
	summary := "🩺 Отчёт проверки серверов (vpncheck)"
	if report.Summary != "" {
		summary = "🩺 " + report.Summary
	}
	if report.Note == "" {
		return summary
	}
	return report.Note + "\n\n" + summary
}
