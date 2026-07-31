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

func equalFold(a, b string) bool { return strings.EqualFold(a, b) }
