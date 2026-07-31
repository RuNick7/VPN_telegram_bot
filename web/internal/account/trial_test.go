package account

import (
	"testing"
	"time"

	"github.com/RuNick7/VPN_telegram_bot/web/internal/store"
)

// The trial is granted when a user's first panel account is created. The
// question these tests pin down is *when that is allowed*, because the
// obvious test -- "does this user have a panel account?" -- is wrong: the
// nightly cleanup deletes the panel account of anyone inactive for a month,
// so it is also false for somebody coming back after a break. Using it would
// make the free period renewable by lapsing.

func service(trialDays int) *Service {
	return NewService(nil, nil, false, trialDays)
}

func user(subscriptionEnds time.Time) *store.User {
	return &store.User{ID: "u1", SubscriptionEnds: subscriptionEnds}
}

// epochZero is what `subscription_ends` holds for an account that has never
// been granted anything -- the column is NOT NULL and defaults to it.
var epochZero = time.Unix(0, 0)

func TestSomeoneWhoHasNeverHadASubscriptionGetsTheTrial(t *testing.T) {
	if !service(30).TrialEligible(user(epochZero)) {
		t.Error("a brand-new account should be eligible")
	}
}

func TestSomeoneComingBackAfterLapsingDoesNotGetAnother(t *testing.T) {
	// Their panel account may well have been deleted by the cleanup, so
	// "has no panel account" is true of them too. `subscription_ends` is the
	// durable record that survives that deletion.
	lapsed := time.Now().AddDate(0, -6, 0)
	if service(30).TrialEligible(user(lapsed)) {
		t.Error("a returning user must not get a second trial")
	}
}

func TestAPayingUserIsNotEligible(t *testing.T) {
	active := time.Now().AddDate(0, 1, 0)
	if service(30).TrialEligible(user(active)) {
		t.Error("an active subscriber should not be handed a trial")
	}
}

func TestTheTrialCanBeSwitchedOff(t *testing.T) {
	if service(0).TrialEligible(user(epochZero)) {
		t.Error("WEB_TRIAL_DAYS=0 must disable the trial entirely")
	}
}

func TestANegativeTrialIsTreatedAsOff(t *testing.T) {
	// Rather than granting negative days, which would create an account
	// already expired *before* now.
	if service(-5).TrialEligible(user(epochZero)) {
		t.Error("a negative trial should be treated as disabled")
	}
}

func TestAZeroTimeIsTreatedAsNeverHavingHadOne(t *testing.T) {
	// A row read before `subscription_ends` was populated scans as the zero
	// time rather than as epoch 0; both mean the same thing here.
	if !service(30).TrialEligible(user(time.Time{})) {
		t.Error("the zero time should count as never having had a subscription")
	}
}
