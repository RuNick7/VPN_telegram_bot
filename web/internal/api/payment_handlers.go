package api

import (
	"errors"
	"fmt"
	"net/http"
	"strings"
	"time"

	"github.com/RuNick7/VPN_telegram_bot/web/internal/pricing"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/quota"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/store"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/yookassa"
)

// Payments are created here and confirmed elsewhere.
//
// Everything below inserts a *pending* row and stops. The Python webhook
// handler is the only thing that moves a payment out of pending, because it is
// the only thing that re-fetches the payment from YooKassa first -- the
// callback body carries no signature and trusting it was a real, shipped
// forgery hole. `store` deliberately offers no way to update a payment's
// status, so this file could not break that rule even by accident.

type paymentResponse struct {
	PaymentID       string `json:"payment_id"`
	ConfirmationURL string `json:"confirmation_url"`
	Amount          int    `json:"amount"`
	Description     string `json:"description"`
}

// payerTelegramID is the Telegram ID to stamp on a payment, or zero.
//
// Zero is fine now. The webhook credits by our own `user_id` and only falls
// back to `telegram_id` for payments created before the identity rework, so an
// account that has never touched Telegram can pay and be credited. The ID is
// still sent when we have one, because it is what makes a charge legible to an
// operator looking at it in YooKassa.
func payerTelegramID(user *store.User) int64 {
	if user.TelegramID == nil {
		return 0
	}
	return *user.TelegramID
}

func (s *Server) createPayment(w http.ResponseWriter, r *http.Request, req yookassa.Request) {
	if !s.cfg.PaymentsEnabled() {
		writeError(w, http.StatusNotImplemented, "payments_disabled", "Оплата временно недоступна.")
		return
	}

	// Longer than the panel ceiling: YooKassa is a third party we cannot
	// restart, and a payment half-created is worse than a slow response.
	ctx, cancel := contextWithTimeout(r, 20*time.Second)
	defer cancel()

	payment, err := s.payments.CreatePayment(ctx, req)
	if err != nil {
		s.log.Error("create payment", "err", err)
		writeError(w, http.StatusBadGateway, "payment_failed", "Не удалось создать платёж. Попробуйте позже.")
		return
	}

	// Recorded after creation so we never hold a row for a payment that does
	// not exist at YooKassa. A failure here is logged and not surfaced: the
	// payment is real and the webhook will insert its own row on confirmation,
	// so blocking the user from paying would be the worse outcome.
	if err := s.store.InsertPendingPayment(ctx, payment.ID); err != nil {
		s.log.Error("record pending payment", "payment_id", payment.ID, "err", err)
	}

	writeJSON(w, http.StatusOK, paymentResponse{
		PaymentID:       payment.ID,
		ConfirmationURL: payment.ConfirmURL,
		Amount:          req.AmountRubles,
		Description:     req.Description,
	})
}

func (s *Server) handleBuySubscription(w http.ResponseWriter, r *http.Request, user *store.User) {
	var body struct {
		Months    int    `json:"months"`
		ReturnURL string `json:"return_url"`
	}
	if err := decodeJSON(r, &body); err != nil {
		writeError(w, http.StatusBadRequest, "bad_request", "Некорректный запрос.")
		return
	}

	// The price is looked up from our table by plan length, never taken from
	// the request. A client that could name its own amount could buy a year
	// for a rouble.
	price, ok := pricing.SubscriptionPrice(body.Months, user.ReferredPeople)
	if !ok {
		writeError(w, http.StatusBadRequest, "unknown_plan", "Такого тарифа нет.")
		return
	}
	s.createPayment(w, r, yookassa.Request{
		AmountRubles: price,
		Description:  fmt.Sprintf("Подписка на %d мес.", body.Months),
		ReturnURL:    s.returnURL(body.ReturnURL),
		TelegramID:   payerTelegramID(user),
		UserID:       user.ID,
		DaysToExtend: pricing.DaysForMonths(body.Months),
		Email:        user.Email,
	})
}

func (s *Server) handleBuyTraffic(w http.ResponseWriter, r *http.Request, user *store.User) {
	if !s.cfg.LTEEnabled {
		writeError(w, http.StatusNotImplemented, "traffic_disabled",
			"Дополнительный трафик сейчас не продаётся.")
		return
	}

	var body struct {
		Gigabytes int    `json:"gigabytes"`
		ReturnURL string `json:"return_url"`
	}
	if err := decodeJSON(r, &body); err != nil {
		writeError(w, http.StatusBadRequest, "bad_request", "Некорректный запрос.")
		return
	}

	price, ok := pricing.TrafficPacks[body.Gigabytes]
	if !ok {
		writeError(w, http.StatusBadRequest, "unknown_pack", "Такого пакета нет.")
		return
	}
	s.createPayment(w, r, yookassa.Request{
		AmountRubles: price,
		Description:  fmt.Sprintf("%s: %d ГБ", quota.TrafficLabel, body.Gigabytes),
		ReturnURL:    s.returnURL(body.ReturnURL),
		TelegramID:   payerTelegramID(user),
		UserID:       user.ID,
		// Zero days on purpose: the webhook branches on lte_gb and must not
		// touch the subscription date for a traffic purchase.
		DaysToExtend: 0,
		LTEGigabytes: body.Gigabytes,
		Email:        user.Email,
	})
}

func (s *Server) handleBuyGift(w http.ResponseWriter, r *http.Request, user *store.User) {
	var body struct {
		Months    int    `json:"months"`
		ReturnURL string `json:"return_url"`
	}
	if err := decodeJSON(r, &body); err != nil {
		writeError(w, http.StatusBadRequest, "bad_request", "Некорректный запрос.")
		return
	}

	// Gifts are priced at tier 0. The referral ladder is a discount on your
	// own subscription; letting it price a gift would turn it into a way to
	// resell cheap subscriptions to other people.
	price, ok := pricing.SubscriptionPrice(body.Months, 0)
	if !ok {
		writeError(w, http.StatusBadRequest, "unknown_plan", "Такого тарифа нет.")
		return
	}
	s.createPayment(w, r, yookassa.Request{
		AmountRubles: price,
		Description:  fmt.Sprintf("Подарочная подписка на %d мес.", body.Months),
		ReturnURL:    s.returnURL(body.ReturnURL),
		TelegramID:   payerTelegramID(user),
		UserID:       user.ID,
		DaysToExtend: pricing.DaysForMonths(body.Months),
		IsGift:       true,
		Email:        user.Email,
	})
}

func (s *Server) handlePaymentStatus(w http.ResponseWriter, r *http.Request, user *store.User) {
	status, err := s.store.PaymentStatus(r.Context(), r.PathValue("id"))
	if errors.Is(err, store.ErrNotFound) {
		writeError(w, http.StatusNotFound, "unknown_payment", "Платёж не найден.")
		return
	}
	if err != nil {
		s.fail(w, r, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"status": status})
}

// returnURL is where YooKassa sends the user back to.
//
// Only a path from the client is honoured, appended to our own origin. Taking
// a full URL would make this an open redirect that a phishing page could point
// anywhere -- and it would arrive stamped with a real payment flow.
func (s *Server) returnURL(requested string) string {
	if strings.HasPrefix(requested, "/") && !strings.HasPrefix(requested, "//") {
		return s.cfg.BaseURL + requested
	}
	return s.cfg.BaseURL + "/"
}
