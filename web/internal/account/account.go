// Package account coordinates the two systems that together make up a
// customer: our database (who they are, what they paid for) and the Remnawave
// panel (their actual VPN access).
//
// Handlers stay thin because this is where the ordering rules live -- most
// importantly that the database and the panel are updated in an order where a
// failure halfway leaves the user with *less* than they paid for rather than
// with access they did not.
package account

import (
	"context"
	"errors"
	"log/slog"
	"time"

	"github.com/RuNick7/VPN_telegram_bot/web/internal/panel"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/store"
)

// freeTierPanelExpiry is how far ahead `expireAt` is pushed when the FREE tier
// owns expiry instead of the panel. Mirrors FREE_TIER_PANEL_EXPIRE_YEARS.
const freeTierPanelExpiryYears = 10

type Service struct {
	store           *store.Store
	panel           *panel.Client
	freeTierEnabled bool
}

func NewService(st *store.Store, pc *panel.Client, freeTierEnabled bool) *Service {
	return &Service{store: st, panel: pc, freeTierEnabled: freeTierEnabled}
}

// panelExpiry is what to write into the panel's `expireAt`.
//
// The real date when the FREE tier is off, so the panel keeps expiring
// accounts exactly as before. A far-future placeholder when it is on, because
// expiry is then enforced by the demotion job moving users between squads --
// an account whose `expireAt` has passed is dead in the panel no matter which
// squad it sits in, including the free one it is supposed to fall back to.
func (s *Service) panelExpiry(subscriptionEnds time.Time) time.Time {
	if !s.freeTierEnabled {
		return subscriptionEnds
	}
	return time.Now().AddDate(freeTierPanelExpiryYears, 0, 0)
}

// EnsureProfile returns the user's panel account, creating it if missing.
//
// Resolution is ordered by how much each handle can be trusted, and matches
// `resolve_panel_user` in user_bot's vpn_service exactly -- the two must find
// the same account for the same person:
//
//  1. the stored UUID, which survives an operator renaming the account;
//  2. the stored username;
//  3. `str(telegram_id)`, the legacy name, for accounts created before the
//     identity rework. Those are deliberately never renamed, so this path
//     stays forever -- but a hit on it backfills the first two, so it is
//     taken at most once per user.
//
// A new profile is created *already expired*. The bot grants its trial on
// /start, tied to a Telegram account; granting one here would grant it per
// email address instead, which is per mailbox. Purchases extend from now, so
// an expired-on-creation profile costs a paying user nothing.
func (s *Service) EnsureProfile(ctx context.Context, user *store.User) (*panel.User, error) {
	if user.RemnawaveUUID != nil && *user.RemnawaveUUID != "" {
		profile, err := s.panel.UserByUUID(ctx, *user.RemnawaveUUID)
		if err == nil {
			return profile, nil
		}
		if !errors.Is(err, panel.ErrUserNotFound) {
			return nil, err
		}
		// Deleted in the panel, or the UUID went stale. Fall through to the
		// name lookups rather than reporting the user as having no account.
	}

	for _, name := range []string{user.RemnawaveUsername, panel.LegacyUsername(user.TelegramID)} {
		if name == "" {
			continue
		}
		profile, err := s.panel.UserByUsername(ctx, name)
		if errors.Is(err, panel.ErrUserNotFound) {
			continue
		}
		if err != nil {
			return nil, err
		}
		s.rememberPanelIdentity(ctx, user, profile)
		return profile, nil
	}

	expiry := user.SubscriptionEnds
	if expiry.IsZero() || expiry.Before(time.Now()) {
		expiry = time.Now()
	}
	username := panel.UsernameFor(user.ID)
	profile, err := s.panel.CreateUser(ctx, username, user.TelegramID, s.panelExpiry(expiry))
	if err != nil {
		return nil, err
	}
	s.rememberPanelIdentity(ctx, user, profile)
	return profile, nil
}

// rememberPanelIdentity backfills the handle we just resolved the slow way.
//
// Failing to store it costs one extra lookup next time and nothing else, so
// it is logged rather than returned.
func (s *Service) rememberPanelIdentity(ctx context.Context, user *store.User, profile *panel.User) {
	if profile == nil || profile.UUID == "" {
		return
	}
	if user.RemnawaveUUID != nil && *user.RemnawaveUUID == profile.UUID {
		return
	}
	if err := s.store.SetPanelIdentity(ctx, user.ID, profile.UUID, profile.Username); err != nil {
		slog.Warn("could not store panel identity", "user", user.ID, "err", err)
		return
	}
	uuid := profile.UUID
	user.RemnawaveUUID, user.RemnawaveUsername = &uuid, profile.Username
}

// SubscriptionURL is the user's connection link.
//
// Handed out regardless of subscription state: an expired subscription means
// fewer servers behind the same link, not no link.
func (s *Service) SubscriptionURL(ctx context.Context, user *store.User) (string, error) {
	profile, err := s.EnsureProfile(ctx, user)
	if err != nil {
		return "", err
	}
	return profile.SubscriptionURL, nil
}

// ResetLink rotates the connection link, invalidating the old one.
func (s *Service) ResetLink(ctx context.Context, user *store.User) (string, error) {
	profile, err := s.EnsureProfile(ctx, user)
	if err != nil {
		return "", err
	}
	revoked, err := s.panel.RevokeSubscription(ctx, profile.UUID)
	if err != nil {
		return "", err
	}
	if revoked.SubscriptionURL != "" {
		return revoked.SubscriptionURL, nil
	}
	// Older panels answer the revoke with a thinner body. The link has already
	// rotated by now, so re-read rather than report a failure that did not
	// happen.
	fresh, err := s.panel.UserByUsername(ctx, profile.Username)
	if err != nil {
		return "", err
	}
	return fresh.SubscriptionURL, nil
}

type Device struct {
	// ID is a hash of the HWID, not the HWID itself: it travels to the browser
	// and back, and a device fingerprint is not ours to publish.
	ID          string `json:"id"`
	Platform    string `json:"platform"`
	OSVersion   string `json:"os_version"`
	DeviceModel string `json:"device_model"`
	CreatedAt   string `json:"created_at"`
}

// Devices lists the user's registered devices and their device limit.
func (s *Service) Devices(ctx context.Context, user *store.User) ([]Device, *int, error) {
	profile, err := s.EnsureProfile(ctx, user)
	if err != nil {
		return nil, nil, err
	}
	raw, err := s.panel.Devices(ctx, profile.UUID)
	if err != nil {
		return nil, nil, err
	}

	devices := make([]Device, 0, len(raw))
	for _, device := range raw {
		if device.HWID == "" {
			continue // nothing could be deleted by it
		}
		devices = append(devices, Device{
			ID:          DeviceID(device.HWID),
			Platform:    device.Platform,
			OSVersion:   device.OSVersion,
			DeviceModel: device.DeviceModel,
			CreatedAt:   device.CreatedAt,
		})
	}
	return devices, profile.HWIDDeviceLimit, nil
}

var ErrDeviceNotFound = errors.New("account: device not found")

// DeleteDevice unregisters one device, addressed by its hashed ID.
//
// The ID is re-resolved against a fresh listing rather than trusted from the
// request: a page can sit open for a long time, and deleting "whatever is in
// that slot now" would be exactly the wrong recovery. A stale ID matches
// nothing and reports not-found instead of removing a different device.
func (s *Service) DeleteDevice(ctx context.Context, user *store.User, deviceID string) error {
	profile, err := s.EnsureProfile(ctx, user)
	if err != nil {
		return err
	}
	raw, err := s.panel.Devices(ctx, profile.UUID)
	if err != nil {
		return err
	}
	for _, device := range raw {
		if device.HWID != "" && DeviceID(device.HWID) == deviceID {
			return s.panel.DeleteDevice(ctx, profile.UUID, device.HWID)
		}
	}
	return ErrDeviceNotFound
}

// ExtendSubscription adds days in our database and pushes the new date to the
// panel.
//
// The database goes first. If the panel write then fails the user is credited
// but not yet enabled, which the reconciliation job repairs on its next pass;
// the reverse order would enable access that no record says was bought.
func (s *Service) ExtendSubscription(ctx context.Context, user *store.User, days int) (time.Time, error) {
	newEnds, err := s.store.ExtendSubscription(ctx, user.ID, days)
	if err != nil {
		return time.Time{}, err
	}
	profile, err := s.EnsureProfile(ctx, user)
	if err != nil {
		return newEnds, err
	}
	// By UUID, not by name: legacy accounts and new ones are named
	// differently, and patching a name that does not exist would silently
	// update nothing while reporting success.
	if err := s.panel.SetExpiryByUUID(ctx, profile.UUID, s.panelExpiry(newEnds)); err != nil {
		return newEnds, err
	}
	return newEnds, nil
}
