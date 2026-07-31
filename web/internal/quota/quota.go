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
	FreeGBOverride   *int
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
	usage := state.LastUsageBytes
	if usage < 0 {
		usage = 0
	}
	if state.CycleStart != nil && cycle > 0 && now.Sub(*state.CycleStart) >= cycle {
		usage = 0
	}

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
