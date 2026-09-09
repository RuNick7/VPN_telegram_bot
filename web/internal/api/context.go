package api

import (
	"context"
	"net/http"
	"time"
)

// contextWithTimeout bounds how long a handler will wait on a slow dependency.
//
// Derived from the request context so a client disconnecting cancels the
// downstream call too, rather than leaving a panel request running for nobody.
func contextWithTimeout(r *http.Request, d time.Duration) (context.Context, context.CancelFunc) {
	return context.WithTimeout(r.Context(), d)
}

// panelTimeout caps a single Remnawave round-trip. Matches the ceiling the bot
// puts on the same calls: a slow panel should produce a retry prompt, not a
// request that hangs until the browser gives up.
const panelTimeout = 10 * time.Second
