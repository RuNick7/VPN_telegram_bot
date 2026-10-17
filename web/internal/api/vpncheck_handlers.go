package api

import (
	"errors"
	"fmt"
	"math"
	"net/http"
	"time"

	"github.com/RuNick7/VPN_telegram_bot/web/internal/account"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/store"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/support"
)

// The vpncheck program: what a subscription's status is, and a report into
// support.
//
// Neither endpoint takes a session. The program has nothing but the
// customer's subscription link, and the link decides whose subscription and
// whose ticket: whoever holds it already uses that customer's VPN. What it
// permits is no more than that -- the status the customer's own app shows,
// and a message in their own ticket -- and nothing here reads a ticket back.

// Attempts per address per hour, both endpoints together. Each one costs a
// panel lookup; a check is minutes long, so a person never comes near this.
const vpncheckAttemptsPerHour = 30

const unknownSubscription = "Подписка не найдена. Если вы сбрасывали ссылку, возьмите новую в боте или в личном кабинете."

// vpncheckCustomer finds whose link this is, answering the program itself
// when it cannot.
func (s *Server) vpncheckCustomer(w http.ResponseWriter, r *http.Request, link string) (*store.User, string, bool) {
	if !s.allowSupport(w, r, "vpncheck:"+clientIP(r), vpncheckAttemptsPerHour,
		"Слишком много попыток. Попробуйте через час.") {
		return nil, "", false
	}
	id, ok := support.SubscriptionID(link)
	if !ok {
		writeError(w, http.StatusBadRequest, "link_invalid", "Это не ссылка на подписку.")
		return nil, "", false
	}
	if s.account == nil {
		writeError(w, http.StatusServiceUnavailable, "unavailable", "Статус подписки сейчас не узнать.")
		return nil, "", false
	}
	ctx, cancel := contextWithTimeout(r, panelTimeout)
	defer cancel()
	user, err := s.account.CustomerBySubscription(ctx, id)
	if errors.Is(err, account.ErrUnknownSubscription) {
		writeError(w, http.StatusNotFound, "subscription_not_found", unknownSubscription)
		return nil, "", false
	}
	if err != nil {
		s.fail(w, r, err)
		return nil, "", false
	}
	return user, id, true
}

type vpncheckStatusBody struct {
	// active: paid or trial time is running. free: it is not, and the free
	// tier keeps some servers open. expired: it is not and nothing is open.
	// none: there never was any.
	State     string `json:"state"`
	ExpiresAt *int64 `json:"expires_at"`
	DaysLeft  int    `json:"days_left"`
	Tier      string `json:"tier"`
	RenewURL  string `json:"renew_url"`
}

// handleVpncheckStatus says what the customer's subscription is, by our
// records rather than the panel's: with the free tier on, the panel holds a
// date ten years out for everyone.
func (s *Server) handleVpncheckStatus(w http.ResponseWriter, r *http.Request) {
	var body struct {
		Link string `json:"link"`
	}
	if err := decodeJSON(r, &body); err != nil {
		writeError(w, http.StatusBadRequest, "bad_request", "Некорректный запрос.")
		return
	}
	user, _, ok := s.vpncheckCustomer(w, r, body.Link)
	if !ok {
		return
	}
	writeJSON(w, http.StatusOK, s.vpncheckStatus(user))
}

func (s *Server) vpncheckStatus(user *store.User) vpncheckStatusBody {
	body := vpncheckStatusBody{Tier: user.SquadTier, RenewURL: s.cfg.BaseURL + "/app/plans"}
	ever := !user.SubscriptionEnds.IsZero() && user.SubscriptionEnds.Unix() > 0
	if ever {
		expires := user.SubscriptionEnds.Unix()
		body.ExpiresAt = &expires
	}
	switch {
	case user.SubscriptionActive():
		body.State = "active"
		// Rounded up, as the cabinet counts them (handleSubscription).
		body.DaysLeft = int(math.Ceil(time.Until(user.SubscriptionEnds).Hours() / 24))
	case s.cfg.FreeTierEnabled:
		body.State = "free"
	case ever:
		body.State = "expired"
	default:
		body.State = "none"
	}
	return body
}

// handleVpncheckReport puts a report into the customer's latest open ticket,
// or opens one with it.
func (s *Server) handleVpncheckReport(w http.ResponseWriter, r *http.Request) {
	if !s.cfg.SupportEnabled {
		writeError(w, http.StatusNotFound, "not_found", "Раздел поддержки недоступен.")
		return
	}
	release, ok := s.acquireUploadSlot(w, r)
	if !ok {
		return
	}
	defer release()

	_ = http.NewResponseController(w).SetReadDeadline(time.Now().Add(uploadReadTimeout))
	r.Body = http.MaxBytesReader(w, r.Body, support.MaxDocumentBytes+1<<20)
	report, err := support.ReadVpncheckReport(r)
	var problem *support.Problem
	if errors.As(err, &problem) {
		writeError(w, problem.Status, problem.Code, problem.Message)
		return
	}
	if err != nil {
		s.fail(w, r, err)
		return
	}
	user, id, ok := s.vpncheckCustomer(w, r, report.Link)
	if !ok {
		return
	}

	file := store.NewSupportFile{
		FileName:    report.File.Name,
		ContentType: report.File.ContentType,
		Data:        support.ScrubReport(report.File.Data, id),
	}
	ticketID, created, err := s.store.AttachVpncheckReport(r.Context(), user.ID, support.ReportSubject,
		support.ReportMessage(report), file, support.ReportsPerDay, support.DailyUploadBytes)
	switch {
	case errors.Is(err, store.ErrReportQuota):
		writeError(w, http.StatusTooManyRequests, "report_quota", fmt.Sprintf(
			"За сутки отправлено уже %d отчётов. Поддержка разбирается с ними — новый можно будет отправить завтра.",
			support.ReportsPerDay))
		return
	case errors.Is(err, store.ErrUploadQuota):
		writeError(w, http.StatusTooManyRequests, "upload_quota", uploadQuotaMessage)
		return
	case err != nil:
		s.fail(w, r, err)
		return
	}
	s.log.Info("vpncheck report attached", "ticket", ticketID, "created", created, "bytes", len(file.Data))
	writeJSON(w, http.StatusCreated, map[string]any{"ticket_id": ticketID, "created": created})
}
