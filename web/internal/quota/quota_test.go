package quota

import (
	"testing"
	"time"
)

const (
	gb    = int64(BytesPerGB)
	cycle = 30 * 24 * time.Hour
)

var now = time.Date(2026, 7, 31, 12, 0, 0, 0, time.UTC)

func state(usage, paid int64, cycleStart *time.Time, override *int) State {
	return State{
		PaidBalanceBytes: paid,
		CycleStart:       cycleStart,
		LastUsageBytes:   usage,
		FreeGBOverride:   override,
	}
}

func at(offset time.Duration) *time.Time {
	t := now.Add(offset)
	return &t
}

func TestUntouchedAllowanceIsFullyAvailable(t *testing.T) {
	if got := Remaining(state(0, 0, at(-time.Hour), nil), 10, cycle, now); got != 10*gb {
		t.Errorf("remaining = %d, want %d", got, 10*gb)
	}
}

func TestUsageIsDeductedFromTheAllowance(t *testing.T) {
	if got := Remaining(state(4*gb, 0, at(-time.Hour), nil), 10, cycle, now); got != 6*gb {
		t.Errorf("remaining = %d, want %d", got, 6*gb)
	}
}

func TestPurchasedTrafficAddsToWhatIsLeft(t *testing.T) {
	if got := Remaining(state(4*gb, 3*gb, at(-time.Hour), nil), 10, cycle, now); got != 9*gb {
		t.Errorf("remaining = %d, want %d", got, 9*gb)
	}
}

func TestUsagePastTheAllowanceLeavesOnlyPurchasedTraffic(t *testing.T) {
	if got := Remaining(state(14*gb, 3*gb, at(-time.Hour), nil), 10, cycle, now); got != 3*gb {
		t.Errorf("remaining = %d, want %d", got, 3*gb)
	}
}

func TestARolledCycleShowsAFreshAllowance(t *testing.T) {
	// The correction this package exists for. A usage reading only means
	// anything inside the window it was taken in; between a rollover and the
	// monitor's next pass, quoting it would tell a user with a full new
	// allowance that they have nothing left.
	if got := Remaining(state(10*gb, 0, at(-2*cycle), nil), 10, cycle, now); got != 10*gb {
		t.Errorf("remaining = %d, want %d", got, 10*gb)
	}
}

func TestUsageInsideTheCurrentCycleStillCounts(t *testing.T) {
	// The rollover correction must not swallow legitimate in-window usage.
	if got := Remaining(state(10*gb, 0, at(-cycle+24*time.Hour), nil), 10, cycle, now); got != 0 {
		t.Errorf("remaining = %d, want 0", got)
	}
}

func TestAUserWhoseCycleNeverStartedGetsTheFullAllowance(t *testing.T) {
	// lte_cycle_start is NULL until the monitor first sees them.
	if got := Remaining(state(0, 0, nil, nil), 10, cycle, now); got != 10*gb {
		t.Errorf("remaining = %d, want %d", got, 10*gb)
	}
}

func TestAPersonalAllowanceOverridesTheGlobalOne(t *testing.T) {
	two := 2
	if got := Remaining(state(0, 0, at(-time.Hour), &two), 10, cycle, now); got != 2*gb {
		t.Errorf("remaining = %d, want %d", got, 2*gb)
	}
}

func TestAZeroOverrideIsARealValueNotAMissingOne(t *testing.T) {
	// 0 means no free traffic at all; only an absent override falls back to
	// the global setting.
	zero := 0
	if got := Remaining(state(0, 0, at(-time.Hour), &zero), 10, cycle, now); got != 0 {
		t.Errorf("remaining = %d, want 0", got)
	}
}

func TestNegativeStoredValuesNeverProduceNegativeRemaining(t *testing.T) {
	if got := Remaining(state(-5, -5, at(-time.Hour), nil), 1, cycle, now); got != 1*gb {
		t.Errorf("remaining = %d, want %d", got, 1*gb)
	}
}

func TestCycleEndsIsAlwaysInTheFuture(t *testing.T) {
	// Even for a user the monitor has not seen in months, the date shown must
	// be the next refresh, not one from the past.
	ends := CycleEnds(state(0, 0, at(-5*cycle), nil), cycle, now)
	if ends == nil {
		t.Fatal("expected a cycle end")
	}
	if !ends.After(now) {
		t.Errorf("cycle ends at %v, which is not after %v", ends, now)
	}
}

func TestNoCycleMeansNoRefreshDate(t *testing.T) {
	if ends := CycleEnds(state(0, 0, nil, nil), cycle, now); ends != nil {
		t.Errorf("expected no cycle end, got %v", ends)
	}
}

func TestTrafficLabelMatchesTheBot(t *testing.T) {
	// The site and the bot must not appear to sell two different products.
	if TrafficLabel != "Трафик белых списков" {
		t.Errorf("label = %q", TrafficLabel)
	}
}

// -- what the screen shows -------------------------------------------------
//
// `used` and `total` are stated by the server rather than worked out from
// `remaining`. The overview used to derive `used = free + purchased -
// remaining`, and purchased traffic appears in both halves of that: once the
// free allowance ran out the two cancelled and the counter froze at exactly the
// free allowance while the traffic drained underneath it. These pin the figures
// against the real readings taken while that was happening.

func spending(usage, spent, paid int64) State {
	return State{
		PaidBalanceBytes: paid,
		CycleStart:       at(-time.Hour),
		LastUsageBytes:   usage,
		CycleSpentBytes:  spent,
	}
}

func TestUsedKeepsMovingPastTheFreeAllowance(t *testing.T) {
	// Two consecutive monitor passes off the live deployment, one gigabyte
	// free. The old derivation reported exactly 1 GB for both.
	first := spending(1_641_282_279, 567_540_455, 583_483_218)
	second := spending(1_749_617_762, 675_875_938, 475_147_735)

	if got := Used(first, cycle, now); got != 1_641_282_279 {
		t.Errorf("used = %d, want the usage reading", got)
	}
	if Used(second, cycle, now) <= Used(first, cycle, now) {
		t.Error("used must rise between passes; it froze before this")
	}
	if Remaining(second, 1, cycle, now) >= Remaining(first, 1, cycle, now) {
		t.Error("remaining must fall between passes")
	}
}

func TestTotalDoesNotShrinkAsTrafficIsCharged(t *testing.T) {
	first := Total(spending(1_641_282_279, 567_540_455, 583_483_218), 1, cycle, now)
	second := Total(spending(1_749_617_762, 675_875_938, 475_147_735), 1, cycle, now)

	if first != second {
		t.Errorf("total moved between passes: %d then %d", first, second)
	}
	if want := int64(BytesPerGB) + 567_540_455 + 583_483_218; first != want {
		t.Errorf("total = %d, want %d (free + spent + held)", first, want)
	}
}

func TestUsedAndRemainingAddUpToTotal(t *testing.T) {
	// The property the screen depends on: the bar, the counter and the
	// "осталось" line are three views of one number and must agree.
	//
	// It holds for states the monitor actually leaves behind -- where overage
	// past the free gigabyte has been charged to the balance. Overage that
	// could not be charged is the exception below, on purpose.
	for _, s := range []State{
		spending(0, 0, 0),
		spending(400*int64(BytesPerMB), 0, 0),
		spending(3*gb, 2*gb, 5*gb),
		spending(1_749_617_762, 675_875_938, 475_147_735),
	} {
		if got, want := Used(s, cycle, now)+Remaining(s, 1, cycle, now), Total(s, 1, cycle, now); got != want {
			t.Errorf("used+remaining = %d, total = %d, for %+v", got, want, s)
		}
	}
}

func TestUnpaidOverageReadsAsAFullBarNotAsNegativeUse(t *testing.T) {
	// Blocked with nothing bought: 200 MB was spent past the allowance and
	// never charged to anything. Used exceeding total is the honest reading,
	// and the bar clamps.
	s := spending(gb+200*int64(BytesPerMB), 0, 0)

	if Used(s, cycle, now) <= Total(s, 1, cycle, now) {
		t.Error("used should exceed the allowance when overage went unpaid")
	}
	if got := Remaining(s, 1, cycle, now); got != 0 {
		t.Errorf("remaining = %d, want 0", got)
	}
}

func TestARolledCycleShowsNothingUsedYet(t *testing.T) {
	s := State{
		PaidBalanceBytes: 2 * gb,
		CycleStart:       at(-2 * cycle),
		LastUsageBytes:   9 * gb,
		CycleSpentBytes:  4 * gb,
	}
	if got := Used(s, cycle, now); got != 0 {
		t.Errorf("used = %d, want 0 -- last cycle's reading means nothing here", got)
	}
	if got, want := Total(s, 1, cycle, now), int64(BytesPerGB)+2*gb; got != want {
		t.Errorf("total = %d, want %d -- spend from the old cycle must not inflate it", got, want)
	}
}
