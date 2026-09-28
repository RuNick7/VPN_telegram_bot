// Package pricing mirrors the bot's price table and discount arithmetic.
//
// It is duplicated rather than shared because there is no sane way for Go to
// import a Python dict, and a website quoting a different price from the bot
// for the same plan would be a straightforward billing bug. The parity tests
// in pricing_test.go pin every cell of the table and every discount against
// the values user_bot/handlers/constants.py and utils.py produce -- if either
// side is edited alone, they fail.
package pricing

import "sort"

// Months a subscription can be bought for.
var Months = []int{1, 3, 6, 12}

// Prices in roubles, indexed by referral tier then by months.
// Tier is the number of people invited, capped at 5.
var Prices = map[int]map[int]int{
	0: {1: 89, 3: 249, 6: 479, 12: 899},
	1: {1: 69, 3: 200, 6: 380, 12: 730},
	2: {1: 49, 3: 140, 6: 270, 12: 520},
	3: {1: 29, 3: 80, 6: 140, 12: 250},
	4: {1: 15, 3: 40, 6: 60, 12: 100},
	5: {1: 9, 3: 25, 6: 40, 12: 59},
}

// MaxTier is the highest referral tier; inviting more stops helping.
const MaxTier = 5

// TrafficPacks maps gigabytes to roubles.
//
// Flat across referral tiers on purpose: traffic is a consumable resold at
// cost, not a plan someone can earn their way down. Stacking the referral
// ladder on it would let a five-referral user buy traffic for a fraction of
// what serving it costs.
var TrafficPacks = map[int]int{5: 49, 10: 59, 15: 79, 30: 119}

// DaysForMonths is how long each plan actually runs.
// A "year" is 360 days here, matching the bot's 12 * 30 -- not 365.
func DaysForMonths(months int) int { return months * 30 }

func Tier(referredPeople int) int {
	if referredPeople < 0 {
		return 0
	}
	if referredPeople > MaxTier {
		return MaxTier
	}
	return referredPeople
}

// SubscriptionPrice returns the price for a plan at a user's referral tier.
// The bool is false for a plan length that is not sold.
func SubscriptionPrice(months, referredPeople int) (int, bool) {
	price, ok := Prices[Tier(referredPeople)][months]
	return price, ok
}

// bulkDiscount is the percent saved versus buying `units` at the smallest
// option's unit rate:
//
//	(1 - price / (units / baseUnits * basePrice)) * 100
//
// Truncated rather than rounded, so an advertised saving is never larger than
// the real one, and floored at zero so something priced *worse* than the
// baseline is never dressed up as a discount.
func bulkDiscount(units, price, baseUnits, basePrice int) int {
	if baseUnits <= 0 || basePrice <= 0 || units <= 0 {
		return 0
	}
	priceAtBaseRate := float64(units) / float64(baseUnits) * float64(basePrice)
	if priceAtBaseRate <= 0 {
		return 0
	}
	discount := int((1 - float64(price)/priceAtBaseRate) * 100)
	if discount < 0 {
		return 0
	}
	return discount
}

// SubscriptionDiscount is the percent saved on a multi-month plan versus
// paying monthly.
//
// Measured at the user's own tier, so it reports the bulk saving alone.
// Comparing a tier-discounted plan against the *full* monthly price would
// double-count: the referral saving would appear inside this percentage as
// well as in the price itself.
func SubscriptionDiscount(months, price, referredPeople int) int {
	if months <= 1 {
		return 0
	}
	monthly, ok := SubscriptionPrice(1, referredPeople)
	if !ok {
		return 0
	}
	return bulkDiscount(months, price, 1, monthly)
}

// TrafficPackDiscount is how much cheaper per gigabyte a pack is than the
// smallest one, which sets the reference rate and is therefore always 0%.
func TrafficPackDiscount(gigabytes, price int) int {
	if len(TrafficPacks) == 0 {
		return 0
	}
	baseGB := 0
	for gb := range TrafficPacks {
		if baseGB == 0 || gb < baseGB {
			baseGB = gb
		}
	}
	return bulkDiscount(gigabytes, price, baseGB, TrafficPacks[baseGB])
}

// Plan is one purchasable subscription option, priced for a specific user.
type Plan struct {
	Months   int    `json:"months"`
	Days     int    `json:"days"`
	Price    int    `json:"price"`
	Discount int    `json:"discount"`
	Label    string `json:"label"`
}

// Pack is one purchasable traffic option.
type Pack struct {
	Gigabytes int `json:"gigabytes"`
	Price     int `json:"price"`
	Discount  int `json:"discount"`
}

var monthLabels = map[int]string{1: "1 месяц", 3: "3 месяца", 6: "6 месяцев", 12: "1 год"}

// PlansFor returns every subscription option priced at this user's tier.
func PlansFor(referredPeople int) []Plan {
	plans := make([]Plan, 0, len(Months))
	for _, months := range Months {
		price, ok := SubscriptionPrice(months, referredPeople)
		if !ok {
			continue
		}
		plans = append(plans, Plan{
			Months:   months,
			Days:     DaysForMonths(months),
			Price:    price,
			Discount: SubscriptionDiscount(months, price, referredPeople),
			Label:    monthLabels[months],
		})
	}
	return plans
}

// PacksSorted returns traffic packs cheapest first, so a client can render
// them without deciding an order of its own.
func PacksSorted() []Pack {
	packs := make([]Pack, 0, len(TrafficPacks))
	for gb, price := range TrafficPacks {
		packs = append(packs, Pack{Gigabytes: gb, Price: price, Discount: TrafficPackDiscount(gb, price)})
	}
	sort.Slice(packs, func(i, j int) bool { return packs[i].Gigabytes < packs[j].Gigabytes })
	return packs
}
