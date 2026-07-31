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
