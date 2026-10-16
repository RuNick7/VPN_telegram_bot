package api

import (
	"encoding/json"
	"errors"
	"net/http"
	"time"

	"github.com/RuNick7/VPN_telegram_bot/web/internal/store"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/support"
)

// Server-check reports from the vpncheck program.
//
// Neither endpoint takes a session. The program runs on the customer's
// computer with nothing but the one-time code user_bot gave them after they
// agreed to the check, and the code decides everything: which ticket, until
// when, and once only. What it permits is what the customer could do signed
// in -- add their own message to their own ticket -- so a leaked code costs no
// more than a message in that ticket until it expires or is used.

// Attempts per address per hour, both endpoints together. A code is 60 bits;
// at this rate guessing one is not a thing that happens.
const diagnosticsAttemptsPerHour = 20

const diagnosticsCodeRefused = "Код не подошёл: он набран с ошибкой, истёк или уже использован. Попросите поддержку прислать новый."

type diagnosticsSessionBody struct {
	TicketID        int64  `json:"ticket_id"`
	Subject         string `json:"subject"`
	SubscriptionURL string `json:"subscription_url"`
	ExpiresAt       int64  `json:"expires_at"`
}

// diagnosticsAllowed applies the switch and the rate limit both endpoints
// share, and reports whether to carry on.
func (s *Server) diagnosticsAllowed(w http.ResponseWriter, r *http.Request) bool {
	if !s.cfg.SupportEnabled {
		writeError(w, http.StatusNotFound, "not_found", "Раздел поддержки недоступен.")
		return false
	}
	return s.allowSupport(w, r, "support-diagnostics:"+clientIP(r), diagnosticsAttemptsPerHour,
		"Слишком много попыток. Попробуйте через час.")
}

// handleDiagnosticsSession checks a code before the program spends minutes
// on the check, and hands it the customer's subscription link so they need
// not find and paste it.
func (s *Server) handleDiagnosticsSession(w http.ResponseWriter, r *http.Request) {
	if !s.diagnosticsAllowed(w, r) {
		return
	}
	var body struct {
		Code string `json:"code"`
	}
	decoder := json.NewDecoder(http.MaxBytesReader(w, r.Body, 1<<10))
	decoder.DisallowUnknownFields()
	if err := decoder.Decode(&body); err != nil {
		writeError(w, http.StatusBadRequest, "bad_request", "Некорректный запрос.")
		return
	}
	hash, ok := support.HashDiagnosticsCode(body.Code)
	if !ok {
		writeError(w, http.StatusNotFound, "code_invalid", diagnosticsCodeRefused)
		return
	}
	grant, err := s.store.DiagnosticsGrant(r.Context(), hash)
	if errors.Is(err, store.ErrNotFound) {
		writeError(w, http.StatusNotFound, "code_invalid", diagnosticsCodeRefused)
		return
	}
	if err != nil {
		s.fail(w, r, err)
		return
	}
	if grant.Status == "closed" {
		writeError(w, http.StatusConflict, "ticket_closed", "Обращение уже закрыто — отчёт в него не отправить.")
		return
	}

	response := diagnosticsSessionBody{
		TicketID:  grant.TicketID,
		Subject:   grant.Subject,
		ExpiresAt: grant.ExpiresAt.Unix(),
	}
	// Best effort: without the link the program asks the customer to paste
	// it, which is a step more and not a failure.
	if s.account == nil {
		// No panel configured (tests): nothing to ask.
	} else if user, err := s.store.UserByIDFollowingMerge(r.Context(), grant.UserID); err != nil {
		s.log.Warn("diagnostics: customer lookup", "ticket", grant.TicketID, "err", err)
	} else if link, err := s.account.SubscriptionURL(r.Context(), user); err != nil {
		s.log.Warn("diagnostics: subscription link", "ticket", grant.TicketID, "err", err)
	} else {
		response.SubscriptionURL = link
	}
	writeJSON(w, http.StatusOK, response)
}

// handleDiagnosticsReport attaches the report to the ticket as the
// customer's message and spends the code.
func (s *Server) handleDiagnosticsReport(w http.ResponseWriter, r *http.Request) {
	if !s.diagnosticsAllowed(w, r) {
		return
	}
	release, ok := s.acquireUploadSlot(w, r)
	if !ok {
		return
	}
	defer release()

	_ = http.NewResponseController(w).SetReadDeadline(time.Now().Add(uploadReadTimeout))
	r.Body = http.MaxBytesReader(w, r.Body, support.MaxDocumentBytes+1<<20)
	report, err := support.ReadDiagnosticsReport(r)
	var problem *support.Problem
	if errors.As(err, &problem) {
		writeError(w, problem.Status, problem.Code, problem.Message)
		return
	}
	if err != nil {
		s.fail(w, r, err)
		return
	}
	hash, ok := support.HashDiagnosticsCode(report.Code)
	if !ok {
		writeError(w, http.StatusNotFound, "code_invalid", diagnosticsCodeRefused)
		return
	}

	body := "🩺 Отчёт проверки серверов (vpncheck)"
	if report.Summary != "" {
		body = "🩺 " + report.Summary
	}
	file := store.NewSupportFile{FileName: report.File.Name, ContentType: report.File.ContentType, Data: report.File.Data}
	ticketID, err := s.store.AttachDiagnosticsReport(r.Context(), hash, body, file, support.DailyUploadBytes)
	switch {
	case errors.Is(err, store.ErrNotFound):
		writeError(w, http.StatusNotFound, "code_invalid", diagnosticsCodeRefused)
		return
	case errors.Is(err, store.ErrTicketClosed):
		writeError(w, http.StatusConflict, "ticket_closed", "Обращение уже закрыто — отчёт в него не отправить.")
		return
	case errors.Is(err, store.ErrUploadQuota):
		writeError(w, http.StatusTooManyRequests, "upload_quota", uploadQuotaMessage)
		return
	case err != nil:
		s.fail(w, r, err)
		return
	}
	s.log.Info("diagnostics report attached", "ticket", ticketID, "bytes", len(file.Data))
	writeJSON(w, http.StatusCreated, map[string]int64{"ticket_id": ticketID})
}
