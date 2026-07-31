package pricing

import "testing"

// The bot and the site must quote the same number for the same plan. These
// tests hold the Go table against the values user_bot/handlers/constants.py
// and utils.py produce; if either side is edited alone, they fail.

func TestPriceTableMatchesTheBot(t *testing.T) {
	// Copied from PRICES in user_bot/handlers/constants.py.
	want := map[int]map[int]int{
		0: {1: 89, 3: 249, 6: 479, 12: 899},
		1: {1: 69, 3: 200, 6: 380, 12: 730},
		2: {1: 49, 3: 140, 6: 270, 12: 520},
		3: {1: 29, 3: 80, 6: 140, 12: 250},
		4: {1: 15, 3: 40, 6: 60, 12: 100},
		5: {1: 9, 3: 25, 6: 40, 12: 59},
	}
	for tier, plans := range want {
		for months, price := range plans {
			got, ok := SubscriptionPrice(months, tier)
			if !ok || got != price {
				t.Errorf("tier %d, %d months = %d (ok=%v), want %d", tier, months, got, ok, price)
			}
		}
	}
}

func TestTrafficPackTableMatchesTheBot(t *testing.T) {
	want := map[int]int{5: 89, 10: 119, 15: 149, 30: 239}
	for gb, price := range want {
		if got := TrafficPacks[gb]; got != price {
			t.Errorf("%d GB = %d, want %d", gb, got, price)
		}
	}
	if len(TrafficPacks) != len(want) {
		t.Errorf("pack count = %d, want %d", len(TrafficPacks), len(want))
	}
}

func TestTierIsCappedAtFive(t *testing.T) {
	// Inviting a sixth person must not fall off the end of the table.
	for _, referred := range []int{5, 6, 50, 1000} {
		if got := Tier(referred); got != MaxTier {
			t.Errorf("Tier(%d) = %d, want %d", referred, got, MaxTier)
		}
	}
	if got := Tier(-3); got != 0 {
		t.Errorf("Tier(-3) = %d, want 0", got)
	}
}

func TestAYearIsThreeHundredSixtyDays(t *testing.T) {
	// 12 * 30, matching the bot. Quoting 365 here would hand out five free
	// days on every annual plan the site sells.
	if got := DaysForMonths(12); got != 360 {
		t.Errorf("DaysForMonths(12) = %d, want 360", got)
	}
}

func TestSubscriptionDiscountsAtTierZero(t *testing.T) {
	// The percentages the bot renders on its plan buttons.
	want := map[int]int{1: 0, 3: 6, 6: 10, 12: 15}
	for months, expected := range want {
		price, _ := SubscriptionPrice(months, 0)
		if got := SubscriptionDiscount(months, price, 0); got != expected {
			t.Errorf("%d months: discount %d%%, want %d%%", months, got, expected)
		}
	}
}

func TestDiscountIsMeasuredAtTheUsersOwnTier(t *testing.T) {
	// Comparing a tier-discounted plan against the *full* monthly price would
	// double-count: the referral saving would show up inside the bulk
	// percentage as well as in the price itself.
	const tier, months = 3, 12
	price, _ := SubscriptionPrice(months, tier)
	monthly, _ := SubscriptionPrice(1, tier)

	want := int((1 - float64(price)/float64(months*monthly)) * 100)
	if got := SubscriptionDiscount(months, price, tier); got != want {
		t.Errorf("discount = %d%%, want %d%%", got, want)
	}
}

func TestTrafficDiscountsMatchTheBot(t *testing.T) {
	want := map[int]int{5: 0, 10: 33, 15: 44, 30: 55}
	for gb, expected := range want {
		if got := TrafficPackDiscount(gb, TrafficPacks[gb]); got != expected {
			t.Errorf("%d GB: discount %d%%, want %d%%", gb, got, expected)
		}
	}
}

func TestDiscountsAreTruncatedNotRounded(t *testing.T) {
	// An advertised saving must never be larger than the real one.
	// 10 GB at the 5 GB rate is 178₽; at 118₽ the real saving is 33.7%.
	if got := TrafficPackDiscount(10, 118); got != 33 {
		t.Errorf("discount = %d%%, want 33%%", got)
	}
}

func TestAMarkupIsNeverShownAsADiscount(t *testing.T) {
	if got := SubscriptionDiscount(3, 999, 0); got != 0 {
		t.Errorf("discount = %d%%, want 0%%", got)
	}
	if got := TrafficPackDiscount(10, 500); got != 0 {
		t.Errorf("discount = %d%%, want 0%%", got)
	}
}

func TestLargerPacksAreNeverWorseValue(t *testing.T) {
	// If a bigger pack cost more per gigabyte, nobody would have a reason to
	// buy one and the discount labels would be lies.
	packs := PacksSorted()
	for i := 1; i < len(packs); i++ {
		previous := float64(packs[i-1].Price) / float64(packs[i-1].Gigabytes)
		current := float64(packs[i].Price) / float64(packs[i].Gigabytes)
		if current > previous {
			t.Errorf("%d GB costs more per GB than %d GB", packs[i].Gigabytes, packs[i-1].Gigabytes)
		}
	}
}

func TestUnknownPlanLengthsAreRefused(t *testing.T) {
	// A client naming its own plan length must not fall through to a price.
	for _, months := range []int{0, 2, 7, 24, -1} {
		if _, ok := SubscriptionPrice(months, 0); ok {
			t.Errorf("%d months should not be purchasable", months)
		}
	}
}

func TestPlansAreListedShortestFirstWithLabels(t *testing.T) {
	plans := PlansFor(0)
	if len(plans) != len(Months) {
		t.Fatalf("got %d plans, want %d", len(plans), len(Months))
	}
	for i, months := range Months {
		if plans[i].Months != months {
			t.Errorf("plan %d is %d months, want %d", i, plans[i].Months, months)
		}
		if plans[i].Label == "" {
			t.Errorf("plan %d has no label", i)
		}
	}
}

func TestPacksAreListedCheapestFirst(t *testing.T) {
	packs := PacksSorted()
	for i := 1; i < len(packs); i++ {
		if packs[i].Gigabytes <= packs[i-1].Gigabytes {
			t.Fatalf("packs are not in ascending order: %v", packs)
		}
	}
}
