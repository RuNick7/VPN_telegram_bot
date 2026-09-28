package auth

import "testing"

// The deployment SNI-routes 443 to the HTTP server over loopback without PROXY
// protocol, so every visitor arrives as 127.0.0.1. Bucketing on that gave the
// whole site one shared allowance, and the caller who exhausted it was told
// the letter had been sent.
func TestAProxiedAddressIsNotTreatedAsAnIdentity(t *testing.T) {
	for _, ip := range []string{"127.0.0.1", "::1", "0.0.0.0", "", "   ", "not-an-ip"} {
		if !untrustedIP(ip) {
			t.Errorf("%q should not be bucketed: every visitor would share it", ip)
		}
	}
}

func TestARealAddressStillCounts(t *testing.T) {
	for _, ip := range []string{"203.0.113.7", "2001:db8::1", "192.168.1.10"} {
		if untrustedIP(ip) {
			t.Errorf("%q is a real client address and should be rate limited", ip)
		}
	}
}
