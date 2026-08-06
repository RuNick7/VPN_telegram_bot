package api

import (
	"errors"
	"math"
	"net/http"
	"time"

	"github.com/RuNick7/VPN_telegram_bot/web/internal/account"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/auth"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/pricing"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/quota"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/store"
)

type meBody struct {
	ID             string `json:"id"`
	Email          string `json:"email"`
	TelegramTag    string `json:"telegram_tag"`
	HasTelegram    bool   `json:"has_telegram"`
	ReferredPeople int    `json:"referred_people"`
	Tier           int    `json:"tier"`
}

func meResponse(user *store.User) meBody {
	return meBody{
		ID:             user.ID,
		Email:          user.Email,
		TelegramTag:    user.TelegramTag,
		HasTelegram:    user.TelegramID != nil,
		ReferredPeople: user.ReferredPeople,
		Tier:           pricing.Tier(user.ReferredPeople),
	}
}

func (s *Server) handleMe(w http.ResponseWriter, r *http.Request, user *store.User) {
	writeJSON(w, http.StatusOK, meResponse(user))
}

func (s *Server) handleUpdateEmail(w http.ResponseWriter, r *http.Request, user *store.User) {
	var body struct {
		Email string `json:"email"`
	}
	if err := decodeJSON(r, &body); err != nil {
		writeError(w, http.StatusBadRequest, "bad_request", "Некорректный запрос.")
		return
	}
	normalized, err := auth.NormalizeEmail(body.Email)
	if err != nil {
		writeError(w, http.StatusBadRequest, "invalid_email", "Проверьте адрес почты.")
		return
	}

	// Changing the address changes which mailbox can sign in as this account,
	// so refusing an address already in use is not just a uniqueness detail --
	// it stops one account being made to shadow another's login route.
	if existing, err := s.store.UserByEmail(r.Context(), normalized); err == nil && existing.ID != user.ID {
		writeError(w, http.StatusConflict, "email_taken", "Этот адрес уже привязан к другому аккаунту.")
		return
	} else if err != nil && !errors.Is(err, store.ErrNotFound) {
		s.fail(w, r, err)
		return
	}

	if err := s.store.SetEmail(r.Context(), user.ID, normalized); err != nil {
		s.fail(w, r, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]string{"email": normalized})
}

// -- subscription -----------------------------------------------------------

type subscriptionBody struct {
	Active          bool   `json:"active"`
	ExpiresAt       *int64 `json:"expires_at"`
	DaysLeft        int    `json:"days_left"`
	SubscriptionURL string `json:"subscription_url"`
	Tier            string `json:"tier"`
}

func (s *Server) handleSubscription(w http.ResponseWriter, r *http.Request, user *store.User) {
	ctx, cancel := contextWithTimeout(r, panelTimeout)
	defer cancel()

	url, err := s.account.SubscriptionURL(ctx, user)
	if err != nil {
		s.fail(w, r, err)
		return
	}

	body := subscriptionBody{
		Active:          user.SubscriptionActive(),
		SubscriptionURL: url,
		Tier:            user.SquadTier,
	}
	if !user.SubscriptionEnds.IsZero() && user.SubscriptionEnds.Unix() > 0 {
		expires := user.SubscriptionEnds.Unix()
		body.ExpiresAt = &expires
		if remaining := time.Until(user.SubscriptionEnds); remaining > 0 {
			// Rounded up, not truncated. Seven days granted became "6 дней"
			// the moment any time passed -- the customer was told they had
			// been short-changed by a day, on the same screen that had just
			// promised seven. Six days and fifteen hours left is six more
			// whole days plus today, and today still works.
			body.DaysLeft = int(math.Ceil(remaining.Hours() / 24))
		}
	}
	writeJSON(w, http.StatusOK, body)
}

func (s *Server) handleResetLink(w http.ResponseWriter, r *http.Request, user *store.User) {
	ctx, cancel := contextWithTimeout(r, panelTimeout)
	defer cancel()

	url, err := s.account.ResetLink(ctx, user)
	if err != nil {
		s.fail(w, r, err)
		return
	}
	s.log.Info("subscription link rotated", "user", user.ID)
	writeJSON(w, http.StatusOK, map[string]string{"subscription_url": url})
}

// -- devices ----------------------------------------------------------------

func (s *Server) handleListDevices(w http.ResponseWriter, r *http.Request, user *store.User) {
	ctx, cancel := contextWithTimeout(r, panelTimeout)
	defer cancel()

	devices, limit, err := s.account.Devices(ctx, user)
	if err != nil {
		s.fail(w, r, err)
		return
	}
	writeJSON(w, http.StatusOK, map[string]any{"devices": devices, "limit": limit})
}

func (s *Server) handleDeleteDevice(w http.ResponseWriter, r *http.Request, user *store.User) {
	ctx, cancel := contextWithTimeout(r, panelTimeout)
	defer cancel()

	err := s.account.DeleteDevice(ctx, user, r.PathValue("id"))
	switch {
	case errors.Is(err, account.ErrDeviceNotFound):
		// Already gone, or an ID from a page left open too long. Reported as
		// not-found rather than deleting whatever occupies that slot now.
		writeError(w, http.StatusNotFound, "device_not_found", "Это устройство уже отключено.")
		return
	case err != nil:
		s.fail(w, r, err)
		return
	}
	s.log.Info("device removed", "user", user.ID)
	writeJSON(w, http.StatusOK, map[string]string{"status": "deleted"})
}

// -- traffic ----------------------------------------------------------------

func (s *Server) handleTraffic(w http.ResponseWriter, r *http.Request, user *store.User) {
	if !s.cfg.LTEEnabled {
		// Reporting a balance nothing meters would be fiction, so say plainly
		// that the feature is off instead of returning zeroes.
		writeJSON(w, http.StatusOK, map[string]any{"enabled": false})
		return
	}

	state := quota.State{
		PaidBalanceBytes: user.LTEPaidBalanceBytes,
		CycleStart:       user.LTECycleStart,
		LastUsageBytes:   user.LTELastUsageBytes,
		CycleSpentBytes:  user.LTECycleSpentBytes,
		FreeGBOverride:   user.LTEFreeGBOverride,
	}
	cycle := time.Duration(s.cfg.LTECycleDays) * 24 * time.Hour
	now := time.Now()

	body := map[string]any{
		"enabled":         true,
		"label":           quota.TrafficLabel,
		"remaining_bytes": quota.Remaining(state, s.cfg.LTEFreeGBPerCycle, cycle, now),
		"free_bytes":      quota.FreeBytes(state, s.cfg.LTEFreeGBPerCycle),
		"purchased_bytes": user.LTEPaidBalanceBytes,
		// Both stated rather than left for the page to subtract one from the
		// other: purchased traffic sits in the balance and in the total at
		// once, so a derived "used" cancels out and stops moving.
		"used_bytes":  quota.Used(state, cycle, now),
		"total_bytes": quota.Total(state, s.cfg.LTEFreeGBPerCycle, cycle, now),
		// Only meaningful with an active subscription: the metered squad is
		// paid-tier only, so a lapsed user cannot spend any of it.
		"available": user.SubscriptionActive(),
	}
	if ends := quota.CycleEnds(state, cycle, now); ends != nil {
		body["cycle_ends_at"] = ends.Unix()
	}
	writeJSON(w, http.StatusOK, body)
}

// -- plans ------------------------------------------------------------------

func (s *Server) handlePlans(w http.ResponseWriter, r *http.Request, user *store.User) {
	body := map[string]any{
		"tier":             pricing.Tier(user.ReferredPeople),
		"referred_people":  user.ReferredPeople,
		"plans":            pricing.PlansFor(user.ReferredPeople),
		"payments_enabled": s.cfg.PaymentsEnabled(),
	}
	// Traffic is only offered when quotas are on; selling what nothing meters
	// would take money for nothing.
	if s.cfg.LTEEnabled {
		body["traffic_packs"] = pricing.PacksSorted()
		body["traffic_label"] = quota.TrafficLabel
	}
	writeJSON(w, http.StatusOK, body)
}

// -- referrals --------------------------------------------------------------

func (s *Server) handleReferrals(w http.ResponseWriter, r *http.Request, user *store.User) {
	writeJSON(w, http.StatusOK, map[string]any{
		"referred_people": user.ReferredPeople,
		"referrer_tag":    user.ReferrerTag,
		// Once set it cannot change, so the client can render the field as
		// permanently read-only rather than offering an edit that will fail.
		"referrer_locked": user.ReferrerTag != "",
		"tier":     pricing.Tier(user.ReferredPeople),
		"max_tier": pricing.MaxTier,
		// What this user is named by when somebody invites *them*. A website
		// account has no Telegram tag, and its address is now a handle the
		// referrer field accepts, so it is no longer "nothing to show".
		"own_tag":   user.TelegramTag,
		"own_email": user.Email,
	})
}

// handleSetReferrer records who invited this customer.
//
// The field takes a Telegram tag or an email address. Only a tag used to be
// accepted, which quietly excluded everyone who joined through the website:
// they have no tag, so there was no way for an invitee to name them and no way
// for them to ever be credited.
func (s *Server) handleSetReferrer(w http.ResponseWriter, r *http.Request, user *store.User) {
	var body struct {
		Tag string `json:"tag"`
	}
	if err := decodeJSON(r, &body); err != nil {
		writeError(w, http.StatusBadRequest, "bad_request", "Некорректный запрос.")
		return
	}
	handle := normalizeReferrerHandle(body.Tag)
	if handle == "" {
		writeError(w, http.StatusBadRequest, "invalid_tag", "Укажите ник или почту пригласившего.")
		return
	}
	if (user.TelegramTag != "" && equalFold(handle, user.TelegramTag)) ||
		(user.Email != "" && equalFold(handle, user.Email)) {
		writeError(w, http.StatusBadRequest, "self_referral", "Нельзя указать самого себя.")
		return
	}

	referrer, err := s.store.UserByReferrerHandle(r.Context(), handle)
	if errors.Is(err, store.ErrNotFound) {
		writeError(w, http.StatusNotFound, "referrer_not_found",
			"Пользователь с таким ником или почтой не найден.")
		return
	}
	if err != nil {
		s.fail(w, r, err)
		return
	}
	if referrer.ID == user.ID {
		writeError(w, http.StatusBadRequest, "self_referral", "Нельзя указать самого себя.")
		return
	}

	// Stored as whatever will find them again at award time, preferring the tag
	// so existing rows and the bot's own field keep the same shape.
	tag := handle
	if referrer.TelegramTag != "" {
		tag = referrer.TelegramTag
	}

	set, err := s.store.SetReferrerTag(r.Context(), user.ID, tag)
	if err != nil {
		s.fail(w, r, err)
		return
	}
	if !set {
		writeError(w, http.StatusConflict, "already_set", "Пригласивший уже указан — изменить его нельзя.")
		return
	}

	// The referrer is credited when this user pays, not now -- matching the
	// bot, where the payment webhook is what calls award_referral. Awarding on
	// naming alone would make the discount ladder free to farm.
	writeJSON(w, http.StatusOK, map[string]any{
		"referrer_tag": tag,
		"detail":       "Бонус будет начислен пригласившему после вашей первой оплаты.",
	})
}
