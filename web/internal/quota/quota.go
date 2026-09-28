// Package quota is the read-only half of the LTE traffic accounting, ported
// from shared/tgvpn_shared/lte_quota.py.
//
// Only the read-only half. Deciding what a user has *left* is safe to compute
// anywhere; deciding what they have *spent* is not, and stays where it is --
// in the Python monitor, whose delta-based writes are what stop a purchase
// landing mid-pass from being erased. Nothing here writes anything.
package quota

import "time"

const (
	BytesPerGB = 1 << 30
	BytesPerMB = 1 << 20
)

// TrafficLabel is what the metered squad is called anywhere a customer sees
// it. Kept identical to the bot's TRAFFIC_LABEL so the site and the bot do not
// appear to sell two different products.
const TrafficLabel = "Трафик белых списков"

// State is the stored per-user quota state this package reads.
type State struct {
	PaidBalanceBytes int64
	CycleStart       *time.Time
	LastUsageBytes   int64
	CycleSpentBytes  int64
	FreeGBOverride   *int
}

// settled returns the readings corrected for a window that has already rolled.
//
// A usage reading only means anything inside the cycle it was taken in. Once
// the window rolls the allowance is fresh and nothing has been measured against
// it yet, so both figures read as zero until the monitor's next pass. Without
// this, a page loaded after a rollover would show last cycle's exhausted
// balance against this cycle's allowance.
func settled(state State, cycle time.Duration, now time.Time) (usage, spent int64) {
	usage, spent = state.LastUsageBytes, state.CycleSpentBytes
	if usage < 0 {
		usage = 0
	}
	if spent < 0 {
		spent = 0
	}
	if state.CycleStart != nil && cycle > 0 && now.Sub(*state.CycleStart) >= cycle {
		return 0, 0
	}
	return usage, spent
}

// FreeBytes is this user's allowance per cycle.
//
// A per-user override wins over the global setting. Zero is a real override
// meaning no free traffic at all, which is why this checks for a nil pointer
// rather than for a zero value.
func FreeBytes(state State, globalFreeGB int) int64 {
	gb := globalFreeGB
	if state.FreeGBOverride != nil {
		gb = *state.FreeGBOverride
	}
	if gb < 0 {
		gb = 0
	}
	return int64(gb) * BytesPerGB
}

// Remaining is what the user still has to spend: unused allowance plus
// purchased traffic.
//
// Computed from stored state alone -- no panel call -- because it backs a
// screen, not enforcement. It is therefore a few minutes stale by
// construction, which is fine for a balance and would not be for a block.
//
// The one correction made here is for a rolled cycle. A usage reading only
// means anything inside the window it was taken in; once the window rolls the
// allowance is fresh and nothing has been measured against it yet. Without
// this, a page loaded after a rollover but before the monitor's next pass
// would show last cycle's exhausted balance against this cycle's allowance.
func Remaining(state State, globalFreeGB int, cycle time.Duration, now time.Time) int64 {
	usage, _ := settled(state, cycle, now)

	free := FreeBytes(state, globalFreeGB)
	unused := free - usage
	if unused < 0 {
		unused = 0
	}
	paid := state.PaidBalanceBytes
	if paid < 0 {
		paid = 0
	}
	return unused + paid
}

// Used is what has gone against the allowance this cycle.
//
// Simply the usage reading, and it is stated rather than left to be worked out
// from the other two. A screen that derived it as `total - remaining` showed a
// figure that stopped moving the moment the free allowance ran out: past that
// point every byte comes off the purchased balance, which sits in *both* of the
// other numbers and cancels itself out. The counter froze at exactly the free
// allowance and stayed there while the traffic drained -- which is the only
// number on the page anyone actually watches.
func Used(state State, cycle time.Duration, now time.Time) int64 {
	usage, _ := settled(state, cycle, now)
	return usage
}

// Total is the whole allowance this cycle: the free part, plus purchased
// traffic both spent and still held.
//
// The spent part has to be in here. Counting only what remains makes the
// allowance shrink every time traffic is charged, so the bar a customer reads
// as "how much of my traffic is gone" would move for two different reasons at
// once and never agree with either number beside it.
func Total(state State, globalFreeGB int, cycle time.Duration, now time.Time) int64 {
	_, spent := settled(state, cycle, now)
	paid := state.PaidBalanceBytes
	if paid < 0 {
		paid = 0
	}
	return FreeBytes(state, globalFreeGB) + spent + paid
}

// CycleEnds is when the current allowance refreshes, or nil if the user has
// never been seen by the monitor and so has no window yet.
func CycleEnds(state State, cycle time.Duration, now time.Time) *time.Time {
	if state.CycleStart == nil || cycle <= 0 {
		return nil
	}
	end := *state.CycleStart
	for !end.After(now) {
		end = end.Add(cycle)
	}
	return &end
}
