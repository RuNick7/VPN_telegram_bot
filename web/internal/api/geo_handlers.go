package api

import (
	"net/http"
	"net/netip"

	"github.com/RuNick7/VPN_telegram_bot/web/internal/geoip"
)

// EnableGeo turns on /api/whereami with an open city database.
func (s *Server) EnableGeo(db *geoip.DB) {
	s.geo = db
}

// handleWhereAmI answers with the city the visitor's address is in, for the
// landing page to start its planet from. Never the address itself, and
// nothing is logged: the answer is a city and a pair of coordinates.
//
// The address comes from clientIP, which takes X-Forwarded-For at its word.
// That is fine here -- a visitor who forges it only moves their own dot --
// and it is why nothing else may ever be decided from this.
//
// 204 means "unknown": no database configured, an address that is not a
// public one (behind a proxy that does not pass the real address, everybody
// is 127.0.0.1), or no city-level answer for it. The page then falls back to
// guessing from the time zone.
func (s *Server) handleWhereAmI(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Cache-Control", "private, no-store")
	if s.geo == nil {
		w.WriteHeader(http.StatusNoContent)
		return
	}
	addr, err := netip.ParseAddr(clientIP(r))
	if err != nil || !publicAddress(addr) {
		w.WriteHeader(http.StatusNoContent)
		return
	}
	place, ok := s.geo.Lookup(addr)
	if !ok {
		w.WriteHeader(http.StatusNoContent)
		return
	}
	writeJSON(w, http.StatusOK, place)
}

func publicAddress(addr netip.Addr) bool {
	addr = addr.Unmap()
	return addr.IsGlobalUnicast() && !addr.IsPrivate() && !addr.IsLoopback()
}
