package api

import "strings"

// normalizeTag strips the decoration people type around a Telegram handle.
//
// Accepts "@nick", "nick", and a pasted "t.me/nick" or profile URL, because
// all three are what a user actually has in their clipboard.
func normalizeTag(raw string) string {
	tag := strings.TrimSpace(raw)
	tag = strings.TrimPrefix(tag, "https://")
	tag = strings.TrimPrefix(tag, "http://")
	tag = strings.TrimPrefix(tag, "t.me/")
	tag = strings.TrimPrefix(tag, "telegram.me/")
	tag = strings.TrimPrefix(tag, "@")
	if index := strings.IndexAny(tag, "/?#"); index >= 0 {
		tag = tag[:index]
	}
	return strings.TrimSpace(tag)
}

// normalizeReferrerHandle cleans up whichever of the two a customer typed.
//
// An address is left alone apart from trimming and case: running it through
// normalizeTag would eat everything from the first `/` on, and `t.me/` is not
// a prefix any email has. The `@` in front of a Telegram tag is the reason the
// two have to be told apart before either is cleaned up at all.
func normalizeReferrerHandle(raw string) string {
	trimmed := strings.TrimSpace(raw)
	// A leading `@` is habit; it belongs to neither form. No address starts
	// with one, so stripping it before the test is safe and forgiving.
	unprefixed := strings.TrimPrefix(trimmed, "@")
	if strings.Contains(unprefixed, "@") {
		return strings.ToLower(unprefixed)
	}
	return normalizeTag(trimmed)
}

func equalFold(a, b string) bool { return strings.EqualFold(a, b) }
