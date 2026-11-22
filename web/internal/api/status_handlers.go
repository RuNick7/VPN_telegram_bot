package api

import (
	"context"
	"net/http"
	"strings"
	"sync"
	"time"

	"github.com/RuNick7/VPN_telegram_bot/web/internal/panel"
	"github.com/RuNick7/VPN_telegram_bot/web/internal/store"
)

// The locations the site draws, in the order it draws them, keyed by the
// country code the panel stores on each node. Nodes elsewhere (the LTE
// servers in Russia, a relay) are not locations a customer picks, so they are
// left out of the picture rather than shown as a fifth dot.
var statusLocations = []struct {
	id      string
	country string
}{
	{"fi", "FI"},
	{"de", "DE"},
	{"nl", "NL"},
	{"fr", "FR"},
}

// locationStatus is one location's health as the cabinet shows it: all its
// nodes up ("ok"), some ("partial"), or none ("down"). Counts only -- no node
// names or addresses leave the server.
type locationStatus struct {
	ID     string `json:"id"`
	State  string `json:"state"`
	Online int    `json:"online"`
	Total  int    `json:"total"`
}

// summarizeNodes groups nodes by location. A disabled node is switched off on
// purpose and counts for nothing; a node the panel cannot reach counts as down.
// A location with no enabled nodes at all is omitted.
func summarizeNodes(nodes []panel.Node) []locationStatus {
	online := map[string]int{}
	total := map[string]int{}
	for _, node := range nodes {
		if node.IsDisabled {
			continue
		}
		code := strings.ToUpper(strings.TrimSpace(node.CountryCode))
		total[code]++
		if node.IsConnected {
			online[code]++
		}
	}
	out := make([]locationStatus, 0, len(statusLocations))
	for _, loc := range statusLocations {
		n := total[loc.country]
		if n == 0 {
			continue
		}
		up := online[loc.country]
		state := "partial"
		switch {
		case up == n:
			state = "ok"
		case up == 0:
			state = "down"
		}
		out = append(out, locationStatus{ID: loc.id, State: state, Online: up, Total: n})
	}
	return out
}

// statusCache keeps the last answer for a minute: every cabinet visit would
// otherwise be a request to the panel, and node health does not change by
// the second. A failed refresh serves the last good answer for a while
// rather than blanking the globe.
//
// A failure is remembered too. The lock is held across the panel call, so
// without that, a panel that is down would have every visitor queue up for a
// full panelTimeout of their own, one after another.
type statusCache struct {
	mu        sync.Mutex
	at        time.Time
	locations []locationStatus
	failedAt  time.Time
	failure   error
}

const (
	statusFresh = time.Minute
	statusStale = 10 * time.Minute
	statusRetry = 15 * time.Second
)

// get returns what to show and when it was checked, calling fetch at most once
// a minute while the panel answers and at most once per statusRetry while it
// does not.
func (c *statusCache) get(now time.Time, fetch func() ([]panel.Node, error)) ([]locationStatus, time.Time, error) {
	c.mu.Lock()
	defer c.mu.Unlock()

	if c.locations != nil && now.Sub(c.at) < statusFresh {
		return c.locations, c.at, nil
	}
	if c.failure == nil || now.Sub(c.failedAt) >= statusRetry {
		nodes, err := fetch()
		if err == nil {
			c.locations, c.at, c.failure = summarizeNodes(nodes), now, nil
			return c.locations, c.at, nil
		}
		c.failure, c.failedAt = err, now
	}
	if c.locations != nil && now.Sub(c.at) < statusStale {
		return c.locations, c.at, nil
	}
	return nil, time.Time{}, c.failure
}

func (s *Server) handleServerStatus(w http.ResponseWriter, r *http.Request, user *store.User) {
	locations, at, err := s.status.get(time.Now(), func() ([]panel.Node, error) {
		// The answer is shared, so one visitor closing the tab must not cancel
		// it -- and be remembered as the panel failing for everyone else.
		ctx, cancel := context.WithTimeout(context.WithoutCancel(r.Context()), panelTimeout)
		defer cancel()
		return s.account.Nodes(ctx)
	})
	if err != nil {
		s.fail(w, r, err)
		return
	}
	writeStatus(w, locations, at)
}

func writeStatus(w http.ResponseWriter, locations []locationStatus, at time.Time) {
	w.Header().Set("Cache-Control", "private, no-store")
	writeJSON(w, http.StatusOK, map[string]any{"locations": locations, "checked_at": at.Unix()})
}
